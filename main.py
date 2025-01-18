import json
import random
import datetime
from math import inf
from tqdm import tqdm
from itertools import batched
from collections import Counter
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor

def flatten(lst):
    # Flattens a list by removing any nested lists
    return [item for sublist in lst for item in sublist]

def shuffled(lst):
    random.shuffle(lst)
    return lst

def increment(dic, key, inc, default=0):
    val = dic.get(key, default)
    dic[key] = val + inc

@dataclass
class Statistic:
    n : int = 0
    accumulator : int = 0
    maximum : int = 0
    minimum : int = inf

    def record(self, value):
        self.accumulator += value
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)
        self.n += 1
    
    def __str__(self):
        return "average: {}, minimum: {}, maximum: {}".format(*self.evaluate())

    def evaluate(self):
        return self.accumulator / self.n, self.minimum, self.maximum

class Experiment:

    def __init__(self, repetitions=1_000, nTeams=2, maxStreak=3, timeCreated:datetime.datetime=datetime.datetime.now()) -> None: 
        self.NREPETITIONS = repetitions
        self.NTEAMS = nTeams
        self.NROUNDS = 2 * (self.NTEAMS-1)
        self.NGAMES = self.NTEAMS * (self.NTEAMS-1)
        self.NGAMESPERROUND = self.NGAMES // self.NROUNDS
        self.MAXSTREAK = maxStreak
        self.maxStreakViolations = {}
        self.doubleRoundRobinViolations = {}
        self.noRepeatViolations = {}
        self.timeCreated = timeCreated

    def gameIdToTeamIds(self, gid):
        host = gid // (self.NTEAMS-1)
        guest = gid % (self.NTEAMS-1)
        if guest >= host:
            guest += 1
        return host, guest

    def teamIdsToGameId(self, host, guest):
        gid = host * (self.NTEAMS - 1) + guest
        if guest > host:
            gid -= 1
        return gid

    def randomRound(self):
        teamIds = list(range(self.NTEAMS))
        shuffledTeamIds = shuffled(teamIds)
        return sorted(list(map(lambda t: self.teamIdsToGameId(*t), batched(shuffledTeamIds, 2))))

    def randomTournament(self): 
        return [[self.gameIdToTeamIds(gid) for gid in self.randomRound()] for _ in range(self.NROUNDS)]

    def countDoubleRoundRobinViolations(self, tournament):
        counter = Counter(flatten(tournament))
        violations = 0
        for host in range(self.NTEAMS):
            for guest in range(host+1, self.NTEAMS):
                violations += abs(1-counter[(host, guest)])
                violations += abs(1-counter[(guest, host)])
        return violations

    def countNoRepeatViolations(self, tournament):
        violations = 0
        for nextRoundNr in range(1, self.NROUNDS):
            currentRoundNr = nextRoundNr-1
            nextRound = tournament[nextRoundNr]
            currentRound = tournament[currentRoundNr]
            for (host, guest) in currentRound:
                if (host, guest) in nextRound:
                    violations+=1
                if (guest, host) in nextRound:
                    violations+=1
        return violations

    def countMaxStreakViolations(self, tournament):
        violations = 0
        streak = {team:(0,0) for team in range(self.NTEAMS)}
        for round in tournament:
            for (host, guest) in round:
                home, away = streak[host]
                if home+1 > self.MAXSTREAK:
                    violations+=1
                streak[host]=(home+1, 0)
                home, away = streak[guest]
                if away+1 > self.MAXSTREAK:
                    violations+=1
                streak[guest]=(0, away+1)
        return violations
    
    def execute(self):
        for repetition in tqdm(range(self.NREPETITIONS), desc="teams:{}".format(self.NTEAMS)):
            tournament = self.randomTournament()
            
            maxStreakViolations = self.countMaxStreakViolations(tournament)
            increment(self.maxStreakViolations, maxStreakViolations, 1)

            doubleRoundRobinViolations = self.countDoubleRoundRobinViolations(tournament)
            increment(self.doubleRoundRobinViolations, doubleRoundRobinViolations, 1)

            noRepeatViolations = self.countNoRepeatViolations(tournament)
            increment(self.noRepeatViolations, noRepeatViolations, 1)

        self.saveResults()

    def saveResults(self):
        with open("output/{}-{}teams-{}reps-maxStreak{}.json".format(self.timeCreated.strftime("%Y%m%d-%H:%M"), self.NTEAMS, self.NREPETITIONS, self.MAXSTREAK), "w") as file:
            json.dump({
                "maxStreakViolations"        : self.maxStreakViolations,
                "noRepeatViolations"         : self.noRepeatViolations,
                "doubleRoundRobinViolations" : self.doubleRoundRobinViolations
            }, file)

def executeExperiment(exp:Experiment):
    random.seed(1)
    exp.execute()
    return exp

def main():
    time = datetime.datetime.now()
    pool = ProcessPoolExecutor()
    experiments = [Experiment(repetitions=1_000, nTeams=nTeams, timeCreated=time, maxStreak=maxStreak) for nTeams in range(4, 52, 2) for maxStreak in range(1, 6)]
    experiments = pool.map(executeExperiment, experiments)
    pool.shutdown()
    
    all_results = {}
    for exp in experiments:
        streak_results = all_results.get("maxStreak={}".format(exp.MAXSTREAK), {})
        streak_results["teams={}".format(exp.NTEAMS)] = {
            "maxStreakViolations":exp.maxStreakViolations,
            "noRepeatViolations":exp.noRepeatViolations,
            "doubleRoundRobinViolations":exp.doubleRoundRobinViolations
        }
        all_results["maxStreak={}".format(exp.MAXSTREAK)] = streak_results
    with open("output/{}-all-results.json".format(time.strftime("%Y%m%d-%H:%M")), "w" ) as file:
        json.dump(all_results, file)
if __name__ == "__main__":
    main()