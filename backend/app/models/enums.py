from enum import Enum


class Platform(str, Enum):
    LEETCODE = "leetcode"
    CODEFORCES = "codeforces"
    CODECHEF = "codechef"
    ATCODER = "atcoder"


class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class SubmissionStatus(str, Enum):
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT = "time_limit_exceeded"
    MEMORY_LIMIT = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILE_ERROR = "compile_error"


class GoalType(str, Enum):
    RATING = "rating"
    PROBLEMS = "problems"
    TOPIC = "topic"
    CONSISTENCY = "consistency"
    CONTEST = "contest"
    PLACEMENT = "placement"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    PAUSED = "paused"


class CoachFeedbackAction(str, Enum):
    SOLVED = "solved"
    SKIPPED = "skipped"
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"


class AchievementCategory(str, Enum):
    PROBLEM = "problem"
    CONTEST = "contest"
    RATING = "rating"
    STREAK = "streak"
    TOPIC = "topic"
    SPECIAL = "special"