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
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    
    
class AchievementCategory(str, Enum):
    PROBLEM = "problem"
    CONTEST = "contest"
    RATING = "rating"
    STREAK = "streak"
    TOPIC = "topic"
    SPECIAL = "special"