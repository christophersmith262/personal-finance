import numpy

class Mortgage:
    
    def __init__(self, home_value = 0, financing = {}, asset = {}):
        """ Creates a Mortgage.
        
           A Mortgage object will provide information about the cost structure of the mortgage.
        """
        
        if "current_value" not in asset:
            asset["current_value"] = home_value
            
        if "tax_rate" not in asset:
            asset["tax_rate"] = 0.01
            
        if "hoa" not in asset:
            asset["hoa"] = 0

        self.home_value = home_value
        self.financing = financing
        self.asset = asset

    def cost(self):
        """ Describes the cost structure of the mortgage.
        
            Returns a dict with keys:
                'initial_cost': The total amount of money required upfront in the loan.
                'down_payment_cost': 'The amount of money put down in the down payment.'
                'percent_down': The down payment size as a percent of total home value.
                'mortgage_size': The total amount borrowed from the bank.
                'mortgage_payment': The amount paid monthly to the bank to repay the loan.
                'pmi_payment': The amount paid monthly in PMI.
                'tax_payment': The amount paid monthly in property taxes.
                'insurance_payment': The amount paid monthly in insurance costs.
                'hoa': The amount paid monthly in HOA costs.
        """
        if self.home_value is 0:
            return {
            }
        
        financing = self.financing
        asset = self.asset
        
        asset_value = asset["current_value"]
        mortgage_size = asset_value - financing["down_payment"]
        initial_cost = mortgage_size * financing["closing_cost"] + financing["down_payment"]
        percent_down = financing["down_payment"] / asset_value
        pmi_payment = self.pmi(mortgage_size, percent_down) / 12
        mortgage_payment = abs(numpy.pmt(financing["interest_rate"] / 12, 12*30, mortgage_size))
        tax_payment = (asset["current_value"] * asset["tax_rate"]) / 12
        insurance_cost = (0.0035 * asset_value) / 12

        return {
            "initial_cost": initial_cost,
            "closing_cost": initial_cost - financing["down_payment"],
            "down_payment_cost": financing["down_payment"],
            "percent_down": percent_down,
            "mortgage_size": mortgage_size,
            "mortgage_payment": mortgage_payment,
            "pmi_payment": pmi_payment,
            "tax_payment": tax_payment,
            "insurance_payment": insurance_cost,
            "hoa": asset["hoa"],
            "monthly_payment": mortgage_payment + pmi_payment + tax_payment + insurance_cost + asset["hoa"],
        }
    
    def isValid(self):
        """ Returns whether the mortgage is valid.
        
            If this returns False, there is no bank that would possible underwrite the loan.
        """
        return self.home_value > 0
    
    def pmi(self, mortgage_size, percent_down):
        """This is an internal helper method for calculating PMI."""
        if percent_down >= .2:
            return 0;
        elif percent_down >= .15:
            return  mortgage_size * 0.0044
        elif percent_down >= .1:
            return  mortgage_size * 0.0059
        elif percent_down >= .05:
            return mortgage_size * 0.0076
        else:
            return mortgage_size * 0.0098
    
class MortgageModel:
    
    def __init__(self, financing):
        """ Creates a MortgageModel.
        
            A MortgageModel can be used to model different buying scenarios under certain
            financing terms.
            
            The financing structure can contain the following keys:
                'interest_rate': The APR of the loan as quoted by the bank. (required)
                'mortgage_term': The number of months of the loan term. (default=30*12)
                'closing_cost': The percentage of the mortgage that closing costs represent. (default=0.05)
        """
        self.financing = financing

    def optimizeTotalHomeValue(self, restrictions, lower_bound=0, upper_bound=0, step=0):
        """ Optimizes to maximize total home value based on financial boundaries.
        
            Restrictions on the boundary problem can be passed in the "restrictions" parameter.
            Valid restrictions are:
              'hoa': The monthly HOA cost. (default=0)
              'max_monthly_payment': The maximum target monthly payment. (default=Inf)
              'max_mortgage': The maximum loan size. (default=Inf)
              'savings': The amount of money to contribute to the cost-of-purchase. (required)
              'tax_rate': The property tax rate. (default=0.0125)
              
            Returns a Mortgage object representing the best-value mortgage.
        """

        restrictions = self.loadRestrictions(restrictions);
        
        if lower_bound is 0:
            lower_bound = restrictions["savings"]
            upper_bound = 9999999
            step = 100000

        if step < 50:
            step = 1

        best_value = {
            "value": 0,
            "mortgage": Mortgage(0, {}, {}),
            "cost": {"monthly_payment": 0},
        }

        j = 0
        for j in numpy.arange(lower_bound, upper_bound, step):
            found_a_match = False

            for i in numpy.arange(0.05, 1.01, 0.001):
                mortgage = self.getMortgage(j, restrictions)
                
                if not mortgage.isValid():
                    continue

                cost = mortgage.cost()
                low_enough_monthly_payment = cost["monthly_payment"] <= restrictions["max_monthly_payment"]
                have_enough_funds = cost["initial_cost"] <= restrictions["savings"]
                is_mortgage_too_big = cost["mortgage_size"] > restrictions["max_mortgage"]
                is_same_value = j == best_value["value"]
                is_lower_monthly_payment = cost["monthly_payment"] < best_value["cost"]["monthly_payment"]
                
                if is_mortgage_too_big:
                    continue
                
                if (low_enough_monthly_payment and have_enough_funds) or (is_same_value and is_lower_monthly_payment):
                    if j > best_value["value"]:
                        found_a_match = True
                        best_value = {
                            "value": j,
                            "mortgage": mortgage,
                            "cost": cost,
                        }

            if not found_a_match:
                upper_bound = j
                break;

        if step is 1:
            return best_value["mortgage"]
        else:
            return self.optimizeTotalHomeValue(restrictions, best_value["value"], upper_bound, step / 2)
        
    def getMortgage(self, home_value, restrictions):
        """ Generates the best possible mortgage (lowest cost) for a target home value.
        
            Restrictions on the boundary problem can be passed in the "restrictions" parameter.
            Valid restrictions are:
              'hoa': The HOA cost. (default=0)
              'savings': The amount of money to contribute to the cost-of-purchase. (required)
              'tax_rate': The property tax rate. (default=0.0125)

            Returns a Mortgage object representing the best-value mortgage.
        """
        
        financing = self.loadFinancing()
        restrictions = self.loadRestrictions(restrictions)
        financing["down_payment"] = home_value - (restrictions["savings"] - home_value) / (financing["closing_cost"] - 1)
        
        # This means the bank would essentially have to lend the closing costs. This isn't a valid loan.
        if financing["down_payment"] < 0:
            return Mortgage(0, {}, {})
        else:
            return Mortgage(home_value, financing, {
                "current_value": home_value,
                "tax_rate": restrictions['tax_rate'],
                "hoa": restrictions["hoa"],
            });
    
    def loadRestrictions(self, restrictions):
        """ Internal helper function to fill in defaults for a restrictions dict."""
        restrictions = restrictions.copy()
        
        if "savings" not in restrictions:
            raise ValueError("'savings' bound must be set in your constraints.")
            
        if restrictions["savings"] < 10000:
            raise ValueError("Your savings are not high enough. Enter a 'savings' constraint of at least 10000.")
            
        if "max_monthly_payment" not in restrictions and "max_mortgage" not in restrictions:
            raise ValueError("You did not't provide any constraints. You must a 'max_monthly_payment' or 'max_mortgage'.")

        if "max_monthly_payment" not in restrictions:
            restrictions["max_monthly_payment"] = 999999999999999999

        if "max_mortgage" not in restrictions:
            restrictions["max_mortgage"] = 999999999999999999

        if "hoa" not in restrictions:
            restrictions["hoa"] = 0
            
        if "tax_rate" not in restrictions:
            restrictions['tax_rate'] = 0.0125
            
        return restrictions
    
    def loadFinancing(self):
        """ Internal helper function to fill in defaults for a financing dict."""
        financing = self.financing.copy()
        
        if "interest_rate" not in financing:
            raise ValueError("'interest_rate' value is required in the financing argument.")
        
        if "mortgage_term" not in financing:
            financing["mortgage_term"] = 30 * 12
            
        if "closing_cost" not in financing:
            financing["closing_cost"] = 0.05
            
        if "down_payment" not in financing:
            financing["down_payment"] = 0
            
        return financing
