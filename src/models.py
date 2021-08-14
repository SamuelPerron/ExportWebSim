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


class Player:
    def __init__(self, line, data):
        self.line = line
        self.position = data['position']
        self.name = data['name']
        self.stats = self.compile_stats()

    def compile_stats(self):
        stats = {
            'wins': 0,
            'losses': 0,
            'goals': 0,
            'passes': 0,
            'points': 0,
            'shots': 0,
            'blocked_shots': 0,
            'ratio': 0,
            'checks': 0,
            'penalities': 0,
            'mins': 0
        }

        games = self.line.games_played
        team = self.line.team
        for game in games:
            if game.result == game.WIN:
                stats['wins'] += 1

            elif game.result == game.LOSS:
                stats['losses'] += 1

            details = game.get_details()
            h2 = details.find(
                'h2', 
                string=re.compile(f'Players - {team.city} {team.name}')
            )
            table = h2.find_next_siblings()[0]
            trs = table.findChildren('tr', recursive=False)[1:]

            for tr in trs:
                tds = tr.findChildren('td', recursive=False)
                if self.name.upper() in str(tds[0]):
                    stats['goals'] += int(tds[1].string)
                    stats['passes'] += int(tds[2].string)
                    stats['points'] += int(tds[3].string)
                    stats['shots'] += int(tds[4].string)
                    stats['blocked_shots'] += int(tds[10].string)
                    stats['ratio'] += int(tds[5].string)
                    stats['checks'] += int(tds[6].string)
                    stats['penalities'] += int(tds[7].string)
                    stats['mins'] += int(tds[8].string)

        return stats

class Line:
    OFFENCE = 'offence'
    DEFENCE = 'defence'
    SIDE_CHOICES = (OFFENCE, DEFENCE)
    LINEUP_FILE = 'lineup.json'

    def __init__(self, team, data):
        self.team = team
        self.id = data['id']
        self.side = data['side'] if data['side'] in self.SIDE_CHOICES else None
        self.line = data['line']
        self.games_played = self.get_games_from_dates(data['games_played'])
        self.players = [Player(self, player) for player in data['players']]
        self.stats = self.compile_stats()

        self.save_to_json()

    def get_games_from_dates(self, dates_groups):
        team_games = self.team.games_by_date
        games = []
        for date_group in dates_groups:
            start_date = datetime.strptime(date_group[0], '%d/%m')

            if start_date.month < 9:
                start_date = start_date.replace(year=start_date.year + 1)

            try:
                end_date = datetime.strptime(date_group[1], '%d/%m')

                if end_date.month < 9:
                    end_date = end_date.replace(year=end_date.year + 1)
            except IndexError:
                end_date = None

            for date in team_games.keys():
                original_date = date
                date = datetime.strptime(date, '%d/%m')

                if date.month < 9:
                    date = date.replace(year=date.year + 1)
                
                if date >= start_date:
                    if end_date:
                        if date <= end_date:
                            games.append(team_games[original_date])

                    else:
                        games.append(team_games[original_date])

        return games

    def compile_stats(self):
        stats = {}

        for player in self.players:
            player_stats = player.stats

            for stat in player_stats.keys():
                if stat not in stats.keys():
                    stats[stat] = 0

                stats[stat] += player_stats[stat]

        stats['wins'] = self.players[0].stats['wins']
        stats['losses'] = self.players[0].stats['losses']
        stats['nb_games_played'] = len(self.games_played)

        return stats

    def get_player_by_name(self, name):
        for player in self.players:
            if player.name == name:
                return player

    def save_to_json(self):
        with open(self.LINEUP_FILE, 'r', encoding='utf-8') as file:
            lines = json.load(file)

            for line in lines:
                if line['id'] == self.id:
                    line['stats'] = self.stats

                    for player in line['players']:
                        player_obj = self.get_player_by_name(player['name'])
                        player['stats'] = player_obj.stats
            
        with open(self.LINEUP_FILE, 'w', encoding='utf-8') as file:
            dump = json.dumps(lines, indent=4)
            file.write(dump)


class Team:
    def __init__(self, name, city):
        self.name = name
        self.city = city
        self.months = self.get_all_months()
        self.games, self.games_by_date = self.get_all_games()
        self.lines = self.get_all_lines()
        self.stats = self.get_all_stats()
        self.compiled_stats = self.compile_stats()

    def get_all_lines(self):
        with open(Line.LINEUP_FILE) as file:
            data = json.load(file)
            lines = []
            for line in data:
                lines.append(
                    Line(self, line)
                )

            return lines

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
        games_by_date = {}
        for month in self.months:
            for game in month.games:
                games.append(game)
                games_by_date[game.date] = game
        
        return games, games_by_date

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