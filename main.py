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
from questions import op_questions, general_questions, lean_questions, qr_questions
from questions import hard_questions
from hard_questions_extra import hard_questions as hard_questions_extra

hard_questions += hard_questions_extra

load_dotenv()
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ADMIN_ID = 710633503

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/ping")
def ping():
    return "OK", 200

Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

class QuizState(StatesGroup):
    category = State()
    question_index = State()
    selected_options = State()

sections = {
    "🧦 ОП": op_questions,
    "📚 Загальні": general_questions,
    "⚙️ LEAN": lean_questions,
    "🗾 QR": qr_questions,
    "💪 Hard Test": hard_questions,
}

def main_keyboard():
    buttons = [types.KeyboardButton(text=section) for section in sections]
    return types.ReplyKeyboardMarkup(
        keyboard=[[button] for button in buttons],
        resize_keyboard=True
    )

@dp.message(F.text.in_(sections.keys()))
async def start_quiz(message: types.Message, state: FSMContext):
    category = message.text
    await state.set_state(QuizState.category)
    await state.update_data(category=category, question_index=0, selected_options=[], wrong_answers=[], temp_selected=set())
    await send_question(message, state)

async def send_question(message_or_callback, state: FSMContext):
    data = await state.get_data()
    questions = sections[data["category"]]
    index = data["question_index"]

    if index >= len(questions):
        # ... (залишай як є — результат, підрахунок, повідомлення)
        return

    question = questions[index]
    options = list(enumerate(question["options"]))
    random.seed(index)
    random.shuffle(options)
    await state.update_data(shuffled_options=options)

    selected = data.get("temp_selected", set())
    buttons = []
    for i, (label, _) in options:
        prefix = "✅ " if i in selected else "▫️ "
        buttons.append([InlineKeyboardButton(text=prefix + label, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if isinstance(message_or_callback, CallbackQuery):
        try:
            await bot.delete_message(message_or_callback.message.chat.id, message_or_callback.message.message_id)
        except:
            pass
        chat_id = message_or_callback.from_user.id
    else:
        chat_id = message_or_callback.chat.id

    if "image" in question:
        image_path = question["image"]
        await bot.send_photo(chat_id, types.FSInputFile(image_path))

    await bot.send_message(chat_id, question["text"], reply_markup=keyboard)


@dp.callback_query(F.data.startswith("opt_"))
async def toggle_option(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected = data.get("temp_selected", set())
    selected ^= {index}
    await state.update_data(temp_selected=selected)

    buttons = []
    for i, (label, _) in data["shuffled_options"]:
        prefix = "✅ " if i in selected else "▫️ "
        buttons.append([InlineKeyboardButton(text=prefix + label, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_reply_markup(reply_markup=keyboard)

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

@dp.callback_query(F.data == "restart")
async def restart_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Вибери розділ для тесту:", reply_markup=main_keyboard())

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
            mark = "☑️" if idx in item["selected"] else "○"
            text += f"{mark} {label}\n"
        selected_text = [item["options"][i][0] for i in item["selected"]] if item["selected"] else ["—"]
        correct_text = [item["options"][i][0] for i in item["correct"]]
        text += f"\n_Твоя відповідь:_ {', '.join(selected_text)}"
        text += f"\n_Правильна відповідь:_ {', '.join(correct_text)}"
        await callback.message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("Вибери розділ для тесту:", reply_markup=main_keyboard())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
