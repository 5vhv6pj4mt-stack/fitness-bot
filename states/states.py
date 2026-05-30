from aiogram.fsm.state import State, StatesGroup


class WorkoutLogging(StatesGroup):
    logging_sets = State()


class FoodLogging(StatesGroup):
    waiting_input = State()


class Setup(StatesGroup):
    waiting_weight = State()
    waiting_calories = State()


class Onboarding(StatesGroup):
    age = State()
    weight = State()
    height = State()
    goal = State()
    experience = State()
    days = State()
    equipment = State()
    injuries = State()
