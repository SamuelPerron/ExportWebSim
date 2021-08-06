import json
import re
import os
import csv
from datetime import datetime

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from utils import Distant


load_dotenv()
distant = Distant()


class ListToCSV:
    @staticmethod
    def to_csv(to_transform, file_name, header_row):
        dir_path = os.environ.get('SAVE_FOLDER')
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)

        with open(f'{dir_path}/{file_name}.csv', mode='w') as file:
            writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)

            if header_row:
                writer.writerow(header_row)
            
            for obj in to_transform:
                writer.writerow(obj.to_csv())


class Team:
    def __init__(self, name, city):
        self.name = name
        self.city = city
        self.months = self.get_all_months()
        self.games = self.get_all_games()
        self.stats = self.get_all_stats()
        self.compiled_stats = self.compile_stats()

    def get_calendar_data_for_month(self, month=0):
        # If the month is '0', then we get sent back the current month
        print(f'Exporting month {month}...', end='\r')

        data = {
            'cid': 39,
            'm': month,
            's': "1",
            'tv': True
        }

        r = distant.post('/Schedule/CalendarInfos/', data)
        
        try:
            result = r.json()
        except json.decoder.JSONDecodeError:
            result = None

        return result

    def get_all_months(self, only_if_games=False):
        months = []
        for i in range(1, 13):
            month = self.get_calendar_data_for_month(i)

            if only_if_games and month:

                if len(month.games) > 0:
                    months.append(Month(month, self))

            elif month:
                months.append(Month(month, self))

        return months

    def get_all_games(self):
        games = []
        for month in self.months:
            for game in month.games:
                games.append(game)
        
        return games

    def get_all_stats(self):
        stats = []
        for game in self.games:
            for stat in game.team_stats:
                stats.append(stat)
        
        return stats

    def compile_stats(self):
        compiled_stats = {}
        for stat in self.stats:
            if stat.name in compiled_stats.keys():
                compiled_stats[stat.name].succeeded += stat.succeeded
                compiled_stats[stat.name].attempted += stat.attempted

            else:
                compiled_stats[stat.name] = CompiledTeamStat(
                    stat.name,
                    stat.succeeded,
                    stat.attempted
                )

        return compiled_stats.values()

    def to_csv(self):
        now = datetime.now().date()

        ListToCSV.to_csv(
            self.games, 
            f'games_{now}', 
            Game.HEADER_ROW
        )

        ListToCSV.to_csv(
            self.compiled_stats, 
            f'compiled_stats_{now}', 
            TeamStat.HEADER_ROW
        )

    def __str__(self):
        return f'<Team {self.city}>'


class TeamStat:
    def __init__(self, team, name, succeeded, attempted):
        self.team = team
        self.name = name
        self.succeeded = succeeded
        self.attempted = attempted

    def percentage(self):
        return self.succeeded / self.attempted

    HEADER_ROW = ['name', 'succeeded', 'attempted', 'percentage']

    def to_csv(self):
        return [self.name, self.succeeded, self.attempted, self.percentage()]

    def __str__(self):
        return f'<TeamStat {self.name} - {round(self.percentage * 100, 2)}%>'


class CompiledTeamStat(TeamStat):
    def __init__(self, name, succeeded, attempted):
        self.name = name
        self.succeeded = succeeded
        self.attempted = attempted


class Game:
    WIN = 'win'
    LOSS = 'loss'

    def __init__(self, id, date, team, opponent, score):
        self.id = id
        self.team = team
        self.opponent = opponent
        self.date = date
        self.score, self.result = self.websim_score_to_real(score)

        details = self.get_details()
        self.team_stats = self.get_team_stats(details)

    def websim_score_to_real(self, websim_score):
        result = websim_score[-1]
        scores = [int(websim_score[0]), int(websim_score[-3])]
        scores.sort()

        score_loss = scores[0]
        score_win = scores[1]

        if result == 'W':
            result = self.WIN
        elif result == 'L':
            result = self.LOSS

        if result == self.WIN:
            score = {
                self.team.city: score_win,
                self.opponent: score_loss
            }

        elif result == self.LOSS:
            score = {
                self.team.city: score_loss,
                self.opponent: score_win
            }

        return score, result

    def get_details(self):
        r = distant.post(f'/Schedule/GameResult/?gameID={self.id}')
        return BeautifulSoup(r.text, 'html.parser')

    def get_team_stats(self, details):
        stats = []
        h2 = details.find('h2', string=re.compile(
            f'Attempted and succeeded plays - {self.team.city}'
        ))
        table = h2.find_next_siblings()[0]
        trs = table.findChildren('tr', recursive=False)[1:]
        
        for tr in trs:
            tds = tr.findChildren('td', recursive=False)
            
            stats.append(TeamStat(
                self.team,
                tds[0].text.strip(),
                int(tds[1].text),
                int(tds[2].text)
            ))

        return stats

    HEADER_ROW = ['id', 'date', 'opponent', 'result', 'score_us', 'score_them']

    def to_csv(self):
        return [
            self.id, 
            self.date,
            self.opponent, 
            self.result, 
            self.score[self.team.city], 
            self.score[self.opponent]
        ]

    def __str__(self):
        return f'<Game {self.id} - {self.result}>'


class Month:
    MONTH_NAMES = (
        'January', 'February', 'March', 'April',
        'May', 'June', 'July', 'August',
        'September', 'October', 'November', 'December'
    )

    def __init__(self, data, team):
        self.month_nb = data['month']
        month_nb_index = self.month_nb - 1
        self.name = self.MONTH_NAMES[month_nb_index]
        self.team = team
        self.games = self.get_games_from_month_data(data)

    def get_games_from_month_data(self, data):
        games = []
        for day in data['games']:

            if day['Simulated']:
                home_city = day['HomeTeam'].split(' ')[0].lower()
                visitor_city = day['AwayTeam'].split(' ')[0].lower()
                self_city = self.team.city.lower()

                opponent = home_city if home_city != self_city else visitor_city
                self_score = day['HomeGoals'] if home_city == self_city else day['AwayGoals']
                opponent_score = day['AwayGoals'] if home_city == self_city else day['HomeGoals']
                game_result = 'W' if self_score > opponent_score else 'L'
                game_score = f'{self_score}-{opponent_score} {game_result}'

                games.append(Game(
                    day['ID'],
                    f"{day['GameDay']}/{self.month_nb}",
                    self.team,
                    opponent,
                    game_score,
                ))
        return games

    def __str__(self):
        return f'<Month - {self.name}>'