"""Models package - import all models so Base.metadata knows about them."""

from app.models.transcript import Transcript, Chunk  # noqa: F401
from app.models.research import ResearchQuery, ResearchAnswer, Citation  # noqa: F401
from app.models.interview import InterviewSession, InterviewMessage  # noqa: F401
from app.models.evaluation import EvalRun, EvalScore, FeedbackAttempt, FailurePattern  # noqa: F401
