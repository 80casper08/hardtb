import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
from questions import op_questions, general_questions, lean_questions, qr_questions, hard_questions

# Завантаження токена
load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Flask сервер для Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/ping")
def ping():
    return "OK", 200

Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# Стани
class QuizState(StatesGroup):
    category = State()
    question_index = State()
    selected_options = State()

# Розділи
sections = {
    "🦮 ОП": op_questions,
    "📚 Загальні": general_questions,
    "⚙️ LEAN": lean_questions,
    "🗞 QR": qr_questions,
    "💪 Hard Test": hard_questions,
}

def main_keyboard():
    buttons = [types.KeyboardButton(text=section) for section in sections]
    return types.ReplyKeyboardMarkup(
        keyboard=[[button] for button in buttons],
        resize_keyboard=True
    )

# Старт тесту
@dp.message(F.text.in_(sections.keys()))
async def start_quiz(message: types.Message, state: FSMContext):
    category = message.text
    await state.set_state(QuizState.category)
    await state.update_data(category=category, question_index=0, selected_options=[], wrong_answers=[])
    await send_question(message, state)

# Надсилання питання
async def send_question(message_or_callback, state: FSMContext):
    data = await state.get_data()
    questions = sections[data["category"]]
    index = data["question_index"]

    if index >= len(questions):
        correct = 0
        wrongs = []
        for i, q in enumerate(questions):
            correct_answers = {j for j, (_, is_correct) in enumerate(q["options"]) if is_correct}
            user_selected = set(data["selected_options"][i])
            if correct_answers == user_selected:
                correct += 1
            else:
                wrongs.append({
                    "question": q["text"],
                    "options": q["options"],
                    "selected": list(user_selected),
                    "correct": list(correct_answers)
                })

        await state.update_data(wrong_answers=wrongs)

        percent = round(correct / len(questions) * 100)
        grade = "❌ Погано"
        if percent >= 90:
            grade = "💯 Відмінно"
        elif percent >= 70:
            grade = "👍 Добре"
        elif percent >= 50:
            grade = "👌 Задовільно"

        result = (
            "📊 *Результат тесту:*\n\n"
            f"✅ *Правильних відповідей:* {correct} з {len(questions)}\n"
            f"📈 *Успішність:* {percent}%\n"
            f"🏆 *Оцінка:* {grade}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Пройти ще раз", callback_data="restart")],
            [InlineKeyboardButton(text="📋 Детальна інформація", callback_data="details")]
        ])

        # ✅ Виправлена відповідь для CallbackQuery
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.answer(result, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await message_or_callback.answer(result, reply_markup=keyboard, parse_mode="Markdown")
        return

    # ... решта коду без змін (залиш її як є)


# Перемикання опцій
@dp.callback_query(F.data == "confirm")
async def confirm_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = list(data.get("temp_selected", set()))
    selected_options = data.get("selected_options", [])
    selected_options.append(selected)
    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback, state)

# Підтвердження відповіді
@dp.callback_query(F.data == "confirm")
async def confirm_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = list(data.get("temp_selected", set()))
    selected_options = data.get("selected_options", [])
    selected_options.append(selected)
    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback, state)

# Детальна інформація
@dp.callback_query(F.data == "details")
async def show_details(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    wrongs = data.get("wrong_answers", [])
    if not wrongs:
        await callback.message.answer("✅ Усі відповіді правильні!")
        return
    for item in wrongs:
        text = f"❌ *{item['question']}*\n"
        for idx, (label, _) in enumerate(item["options"]):
            mark = "☑️" if idx in item["selected"] else "🔘"
            text += f"{mark} {label}\n"
        selected_text = [item["options"][i][0] for i in item["selected"]] if item["selected"] else ["—"]
        correct_text = [item["options"][i][0] for i in item["correct"]]
        text += f"\n_Твоя відповідь:_ {', '.join(selected_text)}"
        text += f"\n_Правильна відповідь:_ {', '.join(correct_text)}"
        await callback.message.answer(text, parse_mode="Markdown")

# Почати заново
@dp.callback_query(F.data == "restart")
async def restart_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Вибери розділ для тесту:", reply_markup=main_keyboard())

# Старт
@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("Вибери розділ для тесту:", reply_markup=main_keyboard())

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

