from aiogram.fsm.state import State, StatesGroup


class WorkoutLogging(StatesGroup):
    logging_sets = State()


class FoodLogging(StatesGroup):
    waiting_input = State()


class NutritionChat(StatesGroup):
    chatting = State()


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


class EditFood(StatesGroup):
    editing_entry = State()   # ждём новый текст/голос для замены записи питания


class EditWorkout(StatesGroup):
    editing_set = State()     # ждём новые значения подхода (формат: "85x6 RPE8")


class ReminderSettings(StatesGroup):
    waiting_time = State()    # ждём ввод времени ЧЧ:ММ для конкретного приёма


class FoodTemplate(StatesGroup):
    waiting_name = State()    # ждём название шаблона
