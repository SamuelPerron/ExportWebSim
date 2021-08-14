from models import Team
import sys

POSSIBLE_COMMANDS = (
    'team_game_stats',
)


if __name__ == '__main__':
    command = sys.argv[1]
    if command not in POSSIBLE_COMMANDS:
        raise ValueError('Impossible command.')

    if command == 'team_game_stats':
        Team('Les Sablonneux', 'Phoenix').to_csv()