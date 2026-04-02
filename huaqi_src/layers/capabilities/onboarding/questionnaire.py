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
        text="你现在最想做成的一件事是什么？可以是工作上的，也可以是生活里的。",
    ),
    Question(
        dimension="challenges",
        text="什么事情最近让你感到卡住或者消耗？",
    ),
    Question(
        dimension="learned",
        text="最近有没有什么让你觉得「哦，原来如此」的认知？可以是读到的、聊到的、经历到的。",
    ),
    Question(
        dimension="narratives",
        text="你会怎么向一个刚认识的朋友介绍自己？",
    ),
    Question(
        dimension="beliefs",
        text="你最看重什么？有没有什么原则是你不愿意妥协的？",
    ),
    Question(
        dimension="models",
        text="你觉得这个世界是怎么运转的？有没有某个框架或者比喻，是你经常用来理解事情的？",
    ),
    Question(
        dimension="strategies",
        text="你面对一个新的困难或挑战时，通常怎么处理？",
    ),
    Question(
        dimension="people",
        text="你生命里现在最重要的几个人是谁？他们对你意味着什么？",
    ),
    Question(
        dimension="shadows",
        text="如果你最了解你的朋友来评价你，他会说你最大的盲点或弱点是什么？",
    ),
    Question(
        dimension="meta",
        text="你希望我在了解你的过程中，特别注意什么？有没有什么是你不想让我记录的？",
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
