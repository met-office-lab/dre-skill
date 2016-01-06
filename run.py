import math

import datapoint

from decision import Action, Score

DATAPOINT_KEY = "41bf616e-7dbc-4066-826a-7270b8da4b93"

class RunAction(Action):
    def getScore(self):
        """ 
        Score for each variable is distance between idean an limit in gaussian space
        Multiplicitavely combines scores for different variables

        """

        def getForecast(condition, instant):
            conn = datapoint.connection(api_key=DATAPOINT_KEY)
            site = conn.get_nearest_site(instant.place.lat, instant.place.lon)
            forecast = conn.get_forecast_for_site(site.id, frequency="3hourly")
            timesteps = [step for step in day.timesteps for day in forecast.days]

            return min(timesteps, key=lambda v: abs(v.date-instant.time))

        normalizeDistance = lambda val, min, max: return (val-min) / (max-min)
        toGaussianSpace = lambda x: return 1.0/math.sqrt(2.0*math.pi) * math.e**(-0.5 * x**2)
        
        combinedScoreValue = 1.0
        for condition in self.config.conditions:
            for instant in self.possibility:
                forecastCondition = getForecast(condition, instant)
                thisMin = forecastCondition > condition.ideal ? condition.ideal : condition.min
                thisMax = forecastCondition > condition.ideal ? condition.max : condition.ideal
                guassianDistance = toGaussianSpace(normalizeDistance(forecastCondition, thisMin, thisMax))
                combinedScoreValue *= gaussianDistance

        return Score(combinedScoreValue, metadata={"log", "Score for each variable is distance between ideal an limit in gaussian space Multiplicitavely combines scores for different variables",
                                                  "conditions": conditions})

