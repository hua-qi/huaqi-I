from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Question:
    dimension: str
    text: str


@dataclass
class AnsweredPair:
    dimension: str
    answer: str


ONBOARDING_QUESTIONS: List[Question] = [
    Question(
        dimension="goals",
        text="你现在最想做成的一件事是什么？是什么在阻止你？",
    ),
    Question(
        dimension="beliefs",
        text="你觉得一个人要做成事，最关键的是什么？",
    ),
    Question(
        dimension="narratives",
        text="你怎么描述自己？有没有一面是你不太愿意承认但确实存在的？",
    ),
    Question(
        dimension="strategies",
        text="你现在用什么方式推进事情？最近学到了什么让你觉得有用？",
    ),
    Question(
        dimension="people",
        text="你生活里现在最重要的1-2个人是谁？你们的关系是什么状态？",
    ),
]


class OnboardingSession:

    def __init__(self) -> None:
        self.current_index: int = 0
        self.answers: Dict[str, Optional[str]] = {}

    def current_question(self) -> Optional[Question]:
        if self.current_index >= len(ONBOARDING_QUESTIONS):
            return None
        return ONBOARDING_QUESTIONS[self.current_index]

    def answer(self, text: str) -> None:
        q = ONBOARDING_QUESTIONS[self.current_index]
        self.answers[q.dimension] = text
        self.current_index += 1

    def skip(self) -> None:
        self.current_index += 1

    def is_complete(self) -> bool:
        return self.current_index >= len(ONBOARDING_QUESTIONS)

    def get_answered_pairs(self) -> List[AnsweredPair]:
        return [
            AnsweredPair(dimension=dim, answer=ans)
            for dim, ans in self.answers.items()
            if ans is not None
        ]


class OnboardingQuestionnaire:

    def __init__(self) -> None:
        self.session = OnboardingSession()
        self._started = False

    def next_prompt(self) -> Optional[str]:
        if self.is_done():
            return None
        q = self.session.current_question()
        if q is None:
            return None
        self._started = True
        return q.text

    def process_answer(self, text: str) -> None:
        self.session.answer(text)

    def process_skip(self) -> None:
        self.session.skip()

    def is_done(self) -> bool:
        return self.session.is_complete()
