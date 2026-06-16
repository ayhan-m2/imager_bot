# ==========================================
# Imager Pro Bot - Asynchronous Ultimate Edition V5.0 (Dynamic UX)
# Core: Exact structural adherence to Original version + Enterprise Fixes & PDF Engine.
# ==========================================

import asyncio
import io
import os
import shutil
import subprocess
import tempfile
import glob
import cv2
import logging
from datetime import datetime
import numpy as np
import aiosqlite
import yt_dlp
import qrcode
import urllib.parse
import aiohttp
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from pdf2docx import Converter
from pypdf import PdfReader, PdfWriter
from PIL.ExifTags import GPSTAGS
from deep_translator import GoogleTranslator
from fpdf import FPDF
import contextlib

from aiogram import Bot, Dispatcher, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, FSInputFile, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter

logging.basicConfig(level=logging.INFO)

# ==========================================
# تنظیمات اصلی
# ==========================================
import os
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = 6783618754           # آیدی عددی شما
CHANNEL_ID = "@ayhan_m2"      
CHANNEL_URL = "https://t.me/ayhan_m2"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==========================================
# مدیریت دیتابیس و تاریخچه کاربران
# ==========================================
async def init_db():
    async with aiosqlite.connect("imager_db.sqlite") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        await db.execute("CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, task TEXT, dt TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        await db.commit()

async def save_user(user_id: int):
    async with aiosqlite.connect("imager_db.sqlite") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def record_task(user_id: int, task: str):
    async with aiosqlite.connect("imager_db.sqlite") as db:
        await db.execute("INSERT INTO actions (user_id, task) VALUES (?, ?)", (user_id, task))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect("imager_db.sqlite") as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            return [row[0] async for row in cursor]

async def is_joined(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator', 'restricted']
    except Exception as e:
        logging.error(f"Channel Auth Error: {e}")
        return False

# ==========================================
# ماشین وضعیت (State Machine)
# ==========================================
class BotStates(StatesGroup):
    ANY_LINK = State()
    UP_AI = State()
    QR_N = State()
    LCK_PDF = State()
    L_PS = State()
    SCAN_INT = State()
    SCAN_WAIT = State()
    AB_IDX = State()
    AB_R = State()
    P_COMP = State()
    VID_C = State()
    AUD_C = State()
    EXIF_L = State()
    FMT_CONV = State()
    GEN_IMG = State()

# ==========================================
# متون ربات
# ==========================================
TEXTS = {
    'fa': {
        'start': "✨ به سیستم هوشمند Imager Pro خوش آمدید.\nلطفاً زبان خود را انتخاب کنید:",
        'join': "🔒 <b>عضویت الزامی است</b>\n\nبرای استفاده از امکانات بی‌نظیر ربات، لطفاً ابتدا در کانال ما عضو شوید و سپس روی دکمه تأیید کلیک کنید:",
        'main_menu': "<b>🛠 منوی ابزارهای هوشمند:</b>\n\nلطفاً یکی از ابزارهای زیر را انتخاب کنید:",
        'help_text': (
            "📚 <b>راهنمای سریع امکانات:</b>\n\n"
            "✨ <b>افزایش کیفیت (Ultra Upscale):</b> بازسازی هوشمند، رنگ‌دهی و 4K سازی عکس‌های قدیمی.\n"
            "🎨 <b>تولید تصویر:</b> ساخت عکس‌های 4K و فوق‌طبیعی با توصیف متنی.\n"
            "📉 <b>فشرده‌سازی:</b> کاهش حجم عکس، ویدیو و صدا.\n"
            "📥 <b>دانلودر:</b> ارسال لینک شبکه‌های اجتماعی جهت دانلود.\n"
            "📸 <b>اسکنر اسناد:</b> تبدیل چندین عکس به یک فایل PDF.\n"
            "🔄 <b>تبدیل فرمت:</b> تبدیل PDF به Word و بالعکس، یا فرمت‌های عکس.\n"
            "🔒 <b>قفل فایل:</b> رمزگذاری امنیتی (AES-256).\n"
            "📍 <b>موقعیت‌یاب:</b> استخراج نقشه محل ثبت عکس.\n"
        ),
        'about_text': "👨‍💻 <b>توسعه‌دهنده و مدیریت:</b>\n@Ayhan_mojarrad\n\n📌 اطلاع‌رسانی‌ها:\n@ayhan_m2",
        'processing': "در حال پردازش... لطفاً صبور باشید",
        'error': "❌ پردازش با خطا مواجه شد. لطفاً دوباره تلاش کنید.",
        'success': "✅ با موفقیت انجام شد.",
        'size_limit': "❌ حجم فایل شما از حد مجاز تلگرام (20 مگابایت) بیشتر است!"
    },
    'en': {
        'start': "✨ Welcome to Imager Pro.\nPlease select your language:",
        'join': "🔒 <b>Join Required</b>\n\nPlease join our channel first, then click Verify:",
        'main_menu': "<b>🛠 Smart Tools Menu:</b>",
        'help_text': "Comprehensive guide inside. Use buttons to navigate.",
        'about_text': "👨‍💻 <b>Developer:</b>\n@Ayhan_mojarrad",
        'processing': "Processing... please wait",
        'error': "❌ An error occurred.",
        'success': "✅ Successfully done.",
        'size_limit': "❌ File size exceeds the 20MB Telegram limit!"
    }
}

# ==========================================
# دکمه‌های شیشه‌ای
# ==========================================
def auth_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 عضویت در کانال" if lang=='fa' else "📢 Join Channel", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ عضو شدم" if lang=='fa' else "✅ I Joined", callback_data="chk_sub")]
    ])

def main_kb(lang, is_admin=False):
    kb = [
        [InlineKeyboardButton(text="🎨 تولید تصویر (AI)" if lang=='fa' else "🎨 Generate Image", callback_data="cb_genimg"), 
         InlineKeyboardButton(text="✨ افزایش کیفیت عکس" if lang=='fa' else "✨ Upscale Image", callback_data="cb_upsc")],
        [InlineKeyboardButton(text="📉 فشرده‌سازی عکس" if lang=='fa' else "📉 Compress Image", callback_data="cb_comp"), 
         InlineKeyboardButton(text="🎞 کاهش حجم ویدیو" if lang=='fa' else "🎞 Compress Video", callback_data="cb_vcmp")],
        [InlineKeyboardButton(text="🔄 تبدیل فرمت فایل" if lang=='fa' else "🔄 Format Converter", callback_data="cb_fmt"), 
         InlineKeyboardButton(text="📸 اسکنر اسناد" if lang=='fa' else "📸 Doc Scanner", callback_data="cb_scn")],
        [InlineKeyboardButton(text="📥 دانلودر شبکه‌ها" if lang=='fa' else "📥 URL Downloader", callback_data="cb_dl"), 
         InlineKeyboardButton(text="🎧 کاهش حجم صدا" if lang=='fa' else "🎧 Compress Audio", callback_data="cb_acmp")],
        [InlineKeyboardButton(text="📍 موقعیت‌ یاب عکس" if lang=='fa' else "📍 Exif Locator", callback_data="cb_loc"),
         InlineKeyboardButton(text="🔳 ساخت QR Code" if lang=='fa' else "🔳 QR Code", callback_data="cb_qr")],
        [InlineKeyboardButton(text="🔒 قفل‌گذاری فایل" if lang=='fa' else "🔒 Lock File", callback_data="cb_sec"),
         InlineKeyboardButton(text="📖 راهنما" if lang=='fa' else "📖 Guide", callback_data="cb_hlp")],
        [InlineKeyboardButton(text="ℹ️ درباره ما" if lang=='fa' else "ℹ️ About", callback_data="cb_abt")]
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="👑 مشاهده آمار سیستم", callback_data="ad_stats"), 
                   InlineKeyboardButton(text="📢 ارسال همگانی", callback_data="ad_br")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def bck_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت" if lang=='fa' else "🔙 Back", callback_data="cb_hm")]])

def end_dl_kb(lang):
    lbl = "📥 راهنمای ذخیره فایل" if lang == 'fa' else "📥 How to Save"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lbl, callback_data="cb_dnlsav")],
        [InlineKeyboardButton(text="🔙 بازگشت" if lang=='fa' else "🔙 Back", callback_data="cb_hm")]
    ])

def form_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Word به PDF", callback_data="cvf_W2P"), InlineKeyboardButton(text="PDF به Word", callback_data="cvf_P2W")],
        [InlineKeyboardButton(text="PNG به JPG", callback_data="cvf_P2J"), InlineKeyboardButton(text="JPG به PNG", callback_data="cvf_J2P")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="cb_hm")]
    ])

def universal_comp_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="25% (خفیف)", callback_data="ucomp_25"),
         InlineKeyboardButton(text="50% (متوسط)", callback_data="ucomp_50"),
         InlineKeyboardButton(text="75% (شدید)", callback_data="ucomp_75")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="cb_hm")]
    ])

# ==========================================
# توابع پشتیبان و رابط کاربری
# ==========================================
def create_safe_temp(suffix=""):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    return tmp.name

async def animated_loading(message: Message, base_text: str):
    frames = ["⏳", "⌛", "🕰", "⏱", "🚀", "⚡️"]
    idx = 0
    try:
        while True:
            anim_text = f"{frames[idx % len(frames)]} {base_text} {frames[(idx+1) % len(frames)]}"
            with contextlib.suppress(Exception):
                await message.edit_text(anim_text)
            idx += 1
            await asyncio.sleep(1.5)
    except asyncio.CancelledError: pass

def progress_bar_maker(current, total, bar_length=10, fill="█", empty="░"):
    percent = int(current / total * 100)
    filled_length = int(bar_length * current // total)
    bar = fill * filled_length + empty * (bar_length - filled_length)
    return f"[{bar}] {percent}%"

# ==========================================
# موتورها
# ==========================================
async def smart_translation_engine(prompt: str):
    try:
        width, height = 1024, 1024
        txt = prompt.lower()
        if "16:9" in txt or "عریض" in txt or "افقی" in txt: width, height = 1920, 1080
        elif "9:16" in txt or "عمودی" in txt or "پرتره" in txt or "استوری" in txt: width, height = 1080, 1920
        
        c_prompt = prompt.replace("عریض","").replace("افقی","").replace("عمودی","").replace("مربعی","")
        en_word = await asyncio.to_thread(lambda: GoogleTranslator(source='fa', target='en').translate(c_prompt) if any('\u0600' <= c <= '\u06FF' for c in prompt) else prompt)
        final_prompt = f"{en_word}, ultra-realistic, RAW photo, 8k resolution, masterpiece, highly detailed, photorealistic, sharp focus, natural lighting, uncensored"
        return final_prompt, width, height
    except:
        return f"{prompt}, ultra-realistic, RAW photo, highly detailed, 8k", 1024, 1024

def process_ultimate_upscale(input_path, output_path):
    img_cv = cv2.imread(input_path)
    if img_cv is None:
        raise ValueError("Invalid Image Format")
        
    if img_cv.shape[0] > 1500 or img_cv.shape[1] > 1500:
        s = 50 
        w = int(img_cv.shape[1] * s / 100)
        h = int(img_cv.shape[0] * s / 100)
        img_cv = cv2.resize(img_cv, (w, h), interpolation=cv2.INTER_AREA)

    dn = cv2.fastNlMeansDenoisingColored(img_cv, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21)
    lab = cv2.cvtColor(dn, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    cl = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    le = cv2.merge((cl.apply(l), a, b))
    ce = cv2.cvtColor(le, cv2.COLOR_LAB2BGR)
    
    img_p = Image.fromarray(cv2.cvtColor(ce, cv2.COLOR_BGR2RGB))
    fil_alg = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
    img_p = img_p.resize((int(img_p.width * 2), int(img_p.height * 2)), fil_alg)
    
    img_p = img_p.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    img_p = ImageEnhance.Sharpness(img_p).enhance(1.5)
    img_p.save(output_path, format='JPEG', quality=100, optimize=True)

def process_yt_dlp(url, temp_dir):
    y_opts = {
        'outtmpl': temp_dir + '/%(title)s.%(ext)s', 
        'format': 'best[ext=mp4][filesize<=49M]/best[filesize<=49M]/bestvideo[filesize<=30M]+bestaudio/best', 
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }
    with yt_dlp.YoutubeDL(y_opts) as dl: 
        dl.download([url])
    fi = glob.glob(temp_dir + "/*.*")
    if fi:
        if os.path.getsize(fi[0]) > 49.5 * 1024 * 1024: return "TOO_LARGE"
        return fi[0]
    return None

async def async_ffmpeg(i_p, o_p, tp, pt):
    if tp == "VID_C":
        q = '28' if pt == 25 else ('32' if pt == 50 else '38')
        br = '128k' if pt == 25 else ('64k' if pt == 50 else '32k')
        pr = await asyncio.create_subprocess_exec('ffmpeg','-y','-i',i_p,'-vcodec','libx264','-crf',q,'-preset','ultrafast','-b:a',br,o_p, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    elif tp == "AUD_C":
        ar = '64k' if pt == 25 else ('32k' if pt == 50 else '16k')
        pr = await asyncio.create_subprocess_exec('ffmpeg','-y','-i',i_p,'-codec:a','libmp3lame','-b:a',ar,'-ac','1',o_p, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await pr.communicate()

def compress_image_sync(i_p, o_p, pt):
    ig = ImageOps.exif_transpose(Image.open(i_p))
    if ig.mode != 'RGB': ig = ig.convert('RGB')
    s = 0.85 if pt==25 else (0.7 if pt==50 else 0.5)
    ql = 85 if pt==25 else (70 if pt==50 else 50)
    fs = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
    ig.resize((int(ig.width*s), int(ig.height*s)), fs).save(o_p, 'JPEG', quality=ql, optimize=True)

async def check_auth(user_id, msg_or_call, lang):
    if user_id == ADMIN_ID: return True
    if not await is_joined(user_id):
        txt = TEXTS[lang]['join']
        if isinstance(msg_or_call, Message): 
            await msg_or_call.answer(txt, reply_markup=auth_kb(lang), parse_mode="HTML")
        else:
            try: await msg_or_call.message.edit_text(txt, reply_markup=auth_kb(lang), parse_mode="HTML")
            except: 
                await msg_or_call.message.delete()
                await msg_or_call.message.answer(txt, reply_markup=auth_kb(lang), parse_mode="HTML")
        return False
    return True

# ==========================================
# فرامین اصلی ربات
# ==========================================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await save_user(message.chat.id)
    await state.update_data(lang='fa')
    
    lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="زبان فـارسی 🇮🇷", callback_data="LN_fa"), 
         InlineKeyboardButton(text="English 🇬🇧", callback_data="LN_en")]
    ])
    await message.answer(f"{TEXTS['fa']['start']}\n\n👑 Developed by @Ayhan_mojarrad", reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("LN_"))
async def lang_handler(call: CallbackQuery, state: FSMContext):
    lang = call.data.split("_")[1]
    await state.update_data(lang=lang)
    if await check_auth(call.from_user.id, call, lang):
        await call.message.edit_text(TEXTS[lang]['main_menu'], reply_markup=main_kb(lang, call.from_user.id == ADMIN_ID), parse_mode="HTML")

@dp.callback_query(F.data == "chk_sub")
async def check_sub_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'fa')
    if await is_joined(call.from_user.id):
        await call.answer("✅ عضویت تایید شد!", show_alert=True)
        await call.message.edit_text(TEXTS[lang]['main_menu'], reply_markup=main_kb(lang, call.from_user.id == ADMIN_ID), parse_mode="HTML")
    else:
        await call.answer("❌ هنوز عضو نشده‌اید!", show_alert=True)

@dp.callback_query(F.data == "cb_hm")
async def back_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'fa')
    
    tmp_pdf = data.get('tmp_pdf_path')
    if tmp_pdf and os.path.exists(tmp_pdf): 
        with contextlib.suppress(Exception): os.unlink(tmp_pdf)
        
    scan_files = data.get('scan_files', [])
    for f in scan_files:
        if os.path.exists(f): 
            with contextlib.suppress(Exception): os.unlink(f)

    await state.clear()
    await state.update_data(lang=lang)
    if await check_auth(call.fromuser.id if hasattr(call, 'fromuser') else call.from_user.id, call, lang):
        try: await call.message.edit_text(TEXTS[lang]['main_menu'], reply_markup=main_kb(lang, call.from_user.id == ADMIN_ID), parse_mode="HTML")
        except: 
            with contextlib.suppress(Exception): await call.message.delete()
            await call.message.answer(TEXTS[lang]['main_menu'], reply_markup=main_kb(lang, call.from_user.id == ADMIN_ID), parse_mode="HTML")

@dp.callback_query(F.data.in_(["cb_hlp", "cb_abt", "cb_dnlsav"]))
async def info_handlers(call: CallbackQuery, state: FSMContext):
    lang = (await state.get_data()).get('lang', 'fa')
    if call.data == "cb_dnlsav":
        return await call.answer("✨ برای ذخیره، روی سه نقطه بالای فایل کلیک کرده و Save to Downloads را بزنید.", show_alert=True)
    
    text = TEXTS[lang]['help_text'] if call.data == "cb_hlp" else TEXTS[lang]['about_text']
    try: await call.message.edit_text(text, reply_markup=bck_kb(lang), parse_mode="HTML")
    except: 
        with contextlib.suppress(Exception): await call.message.delete()
        await call.message.answer(text, reply_markup=bck_kb(lang), parse_mode="HTML")

state_map = {
    "cb_genimg": (BotStates.GEN_IMG, "🎨 لطفاً سوژه و تصویری که در ذهن دارید را بنویسید (جهت سایز خاص می‌توانید «16:9» یا «عمودی/عریض» اضافه کنید):"),
    "cb_dl": (BotStates.ANY_LINK, "📥 لطفاً لینک ویدیو یا پست مورد نظر را ارسال کنید:"),
    "cb_upsc": (BotStates.UP_AI, "✨ لطفاً عکس بی‌کیفیت یا قدیمی خود را ارسال کنید:"),
    "cb_qr": (BotStates.QR_N, "🔳 متن یا لینک خود را جهت تبدیل به بارکد ارسال کنید:"),
    "cb_sec": (BotStates.LCK_PDF, "🔒 لطفاً فایل یا عکس خود را جهت رمزگذاری ارسال کنید:"),
    "cb_comp": (BotStates.P_COMP, "📉 لطفاً عکس خود را جهت کاهش حجم ارسال کنید:"),
    "cb_loc": (BotStates.EXIF_L, "📍 ⚠️ عکس را حتماً به صورت <b>فایل (Document)</b> ارسال کنید:"),
    "cb_scn": (BotStates.SCAN_INT, "📸 مجموع برگه‌های شما چند عدد است؟ (مثال: 4)"),
    "cb_vcmp": (BotStates.VID_C, "🎞 لطفاً ویدیوی خود را ارسال کنید (حداکثر 20MB):"),
    "cb_acmp": (BotStates.AUD_C, "🎧 لطفاً فایل صوتی یا وویس خود را ارسال کنید:")
}

@dp.callback_query(F.data.in_(list(state_map.keys())))
async def set_state_handlers(call: CallbackQuery, state: FSMContext):
    await record_task(call.from_user.id, f"Initiated state {call.data}")
    lang = (await state.get_data()).get('lang', 'fa')
    target_state, text = state_map[call.data]
    await state.set_state(target_state)
    await call.message.edit_text(text, reply_markup=bck_kb(lang), parse_mode="HTML")

@dp.callback_query(F.data == "cb_fmt")
async def fmt_menu(call: CallbackQuery, state: FSMContext):
    lang = (await state.get_data()).get('lang', 'fa')
    await state.set_state(BotStates.FMT_CONV)
    await call.message.edit_text("🔄 نوع تبدیل را انتخاب کنید:", reply_markup=form_kb(lang))

@dp.callback_query(F.data.startswith("cvf_"))
async def fmt_select(call: CallbackQuery, state: FSMContext):
    lang = (await state.get_data()).get('lang', 'fa')
    await state.update_data(target_fmt=call.data.split("_")[1])
    await call.message.edit_text("📁 لطفاً فایل خود را جهت تبدیل ارسال کنید:", reply_markup=bck_kb(lang))

# ==========================================
# منوی مدیریت و خروجی PDF
# ==========================================
@dp.callback_query(F.data == "ad_stats")
async def admin_stats_generate_pdf(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    wait_msg = await call.message.answer(f"👑 استخراج و ساخت آمار PDF مدیریت سیستم...\n{progress_bar_maker(1, 10)}")
    
    users = await get_all_users()
    
    async with aiosqlite.connect("imager_db.sqlite") as db:
        async with db.execute("SELECT user_id, task, dt FROM actions ORDER BY id DESC LIMIT 500") as cursor:
            records = await cursor.fetchall()
            
    def create_pdf_log():
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 15)
        pdf.cell(0, 10, txt="System Architecture Log - Imager Pro V5", ln=True, align="C")
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 10, txt=f"Date: {datetime.now().strftime('%Y-%m-%d')} | Users Total: {len(users)}", ln=True)
        pdf.line(10, 30, 200, 30)
        
        user_list_text = ", ".join(map(str, users))
        safe_user_text = user_list_text[:3000].encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 5, txt=f"Members Registry Data: {safe_user_text}") 
        pdf.cell(0, 10, txt=f"===== ACTION REGISTRY (Recent Events) =====", ln=True)
        
        for rx in records: 
            safe_task = str(rx[1][:50]).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 6, txt=f"[UID: {rx[0]}] - TASK: {safe_task} | TIME: {rx[2]}", ln=True)

        tf_name = create_safe_temp(".pdf")
        pdf.output(tf_name)
        return tf_name
    
    await wait_msg.edit_text(f"👑 درحال تزریق جداول اطلاعات دیتابیس در PDF\n{progress_bar_maker(7, 10)}")
    pdf_out = None
    try:
        pdf_out = await asyncio.to_thread(create_pdf_log)
        await wait_msg.delete()
        await call.message.answer_document(FSInputFile(pdf_out, filename="SysLog_FullReport.pdf"), caption=f"👑 <b>آمار سیستم استخراج گردید.</b>\n\nتعداد کل کاربران فعال ثبت شده: {len(users)}", parse_mode="HTML")
    except Exception as xErr: 
        logging.error(f"pdf adm_issue: {xErr}")
        await wait_msg.edit_text("❌ خطا در اجرای استخراج FPDF رخ داد.")
    finally:
        if isinstance(pdf_out, str) and os.path.exists(pdf_out): 
            with contextlib.suppress(Exception): os.unlink(pdf_out)

@dp.callback_query(F.data == "ad_br")
async def admin_br(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ارسال به آیدی خاص", callback_data="ab_idd")],
        [InlineKeyboardButton(text="ارسال همگانی", callback_data="ab_bld")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="cb_hm")]
    ])
    await call.message.edit_text("یک گزینه را انتخاب کنید:", reply_markup=kb)

@dp.callback_query(F.data.in_(["ab_idd", "ab_bld"]))
async def admin_br_select(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    if call.data == "ab_idd":
        await state.set_state(BotStates.AB_IDX)
        await call.message.edit_text("لطفاً آیدی عددی کاربر را بفرستید:")
    else:
        await state.set_state(BotStates.AB_R)
        await call.message.edit_text("لطفاً پیام خود را جهت ارسال همگانی بفرستید:")

@dp.message(StateFilter(BotStates.AB_IDX))
async def admin_set_id(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(target_id=message.text)
    await state.set_state(BotStates.AB_R)
    await message.reply("📝 پیام خود را بنویسید (ارسال به شخص):")

@dp.message(StateFilter(BotStates.AB_R))
async def admin_do_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    tid = data.get('target_id')
    
    if tid: 
        try:
            await bot.send_message(tid, f"⚡ <b>پیام مدیریت:</b>\n\n{message.text}", parse_mode="HTML")
            await message.reply("✅ ارسال شد.")
        except: await message.reply("❌ خطا در ارسال.")
        await state.clear()
    else:
        wait_msg = await message.reply(f"🚀 شروع ارسال همگانی...\n{progress_bar_maker(0, 100, bar_length=15)}")
        users = await get_all_users()
        total = len(users)
        success = 0
        
        for idx, u in enumerate(users, 1):
            try:
                await bot.copy_message(chat_id=u, from_chat_id=message.chat.id, message_id=message.message_id)
                success += 1
            except: 
                async with aiosqlite.connect("imager_db.sqlite") as db:
                    await db.execute("DELETE FROM users WHERE user_id = ?", (u,))
                    await db.commit()
            
            if idx % 10 == 0 or idx == total:
                with contextlib.suppress(Exception): 
                    await wait_msg.edit_text(f"🚀 در حال ارسال...\n{progress_bar_maker(idx, total, bar_length=15)}\nوضعیت پرتاب {idx}/{total}")
            await asyncio.sleep(0.05)
            
        await wait_msg.edit_text(f"✅ ارسال پایان یافت.\nموفق: {success}\nناموفق (حذف شدند): {total - success}")
        await state.clear()

# ==========================================
# سیستم ابزارهای غیر مدیایی
# ==========================================
@dp.message(StateFilter(BotStates.GEN_IMG))
async def text_gen_img(message: Message, state: FSMContext):
    lang = (await state.get_data()).get('lang', 'fa')
    s_id = await message.answer("🚀🎨") 
    
    wait_msg = await message.reply(f"🎨 در حال خلق تصویر 4K... لطفاً صبور باشید.\n{progress_bar_maker(0, 10, bar_length=12, fill='█', empty='░')}")
    anim_task = asyncio.create_task(animated_loading(wait_msg, "در حال خلق تصویر هوشمند"))
    
    tmp_img_name = create_safe_temp(".jpg")
    try:
        safe_en_translated, rx_W, rx_H = await smart_translation_engine(message.text)
        await asyncio.sleep(1) 
        
        URL_API = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(safe_en_translated)}?width={rx_W}&height={rx_H}&model=flux&nologo=true&enhance=false"
        
        async with aiohttp.ClientSession() as ssn:
            async with ssn.get(URL_API, headers={'User-Agent': 'Mozilla/5.0'}, timeout=50) as fetcher:
                if fetcher.status == 200:
                    with open(tmp_img_name, 'wb') as f:
                        f.write(await fetcher.read())
                else:
                    raise Exception(f"AI API HTTP {fetcher.status}")
                
        if os.path.getsize(tmp_img_name) < 1000: 
            raise Exception("Invalid image data received.")
        
        anim_task.cancel()
        cap = f"✨ تصویر شما با موفقیت خلق شد.\n\nتوصیف ربات/هوشمند:\n<code>{safe_en_translated}</code>\n\nابعاد نهایی شده خروجی: ({rx_W}x{rx_H})\n@Ayhan_mojarrad"
        await message.answer_photo(FSInputFile(tmp_img_name), caption=cap, parse_mode="HTML", reply_markup=end_dl_kb(lang))
        await state.clear()
        
    except Exception as xErr:
        logging.error(f"Image creation error: {xErr}")
        anim_task.cancel()
        with contextlib.suppress(Exception):
            await wait_msg.edit_text("❌ متأسفانه ارتباط با سرور هوش مصنوعی برقرار نشد. ممکن است کلمه شما غیرمجاز باشد.", reply_markup=bck_kb(lang))
    finally:
        if not anim_task.done(): anim_task.cancel()
        with contextlib.suppress(Exception): await wait_msg.delete()
        with contextlib.suppress(Exception): await s_id.delete()
        if os.path.exists(tmp_img_name): 
            with contextlib.suppress(Exception): os.unlink(tmp_img_name)

@dp.message(StateFilter(BotStates.ANY_LINK))
async def text_dl_link(message: Message, state: FSMContext):
    lang = (await state.get_data()).get('lang', 'fa')
    wait_msg = await message.reply("⏳ در حال استخراج مدیا...")
    anim_task = asyncio.create_task(animated_loading(wait_msg, TEXTS[lang]['processing']))
    
    temp_dir = tempfile.mkdtemp()
    try:
        file_path = await asyncio.to_thread(process_yt_dlp, message.text, temp_dir)
        anim_task.cancel()
        if file_path == "TOO_LARGE":
            await wait_msg.edit_text("❌ فایل نهایی این لینک بالای 50 مگابایت است.", reply_markup=bck_kb(lang))
        elif file_path:
            await message.answer_document(FSInputFile(file_path), caption="✅ فایل دانلود شد.\n@Ayhan_mojarrad", reply_markup=end_dl_kb(lang))
        else:
            await wait_msg.edit_text("❌ دانلود ناموفق بود. لینک خراب است.", reply_markup=bck_kb(lang))
    except Exception as e:
        anim_task.cancel()
        await wait_msg.edit_text("❌ خطا در سیستم دانلود.", reply_markup=bck_kb(lang))
    finally:
        if not anim_task.done(): anim_task.cancel()
        with contextlib.suppress(Exception): await wait_msg.delete()
        shutil.rmtree(temp_dir, ignore_errors=True)

@dp.message(StateFilter(BotStates.SCAN_INT))
async def text_scan_int(message: Message, state: FSMContext):
    lang = (await state.get_data()).get('lang', 'fa')
    if message.text.isdigit() and 1 <= int(message.text) <= 100:
        total = int(message.text)
        await state.update_data(scan_count=total, scan_files=[])
        await state.set_state(BotStates.SCAN_WAIT)
        
        status_msg = await message.answer(
            f"📸 <b>در حال دریافت تصاویر...</b>\n\n{progress_bar_maker(0, total, min(total,12), fill='🟢', empty='⚪️')}\nدریافت شده: 0 از {total}",
            parse_mode="HTML", reply_markup=bck_kb(lang))
        await state.update_data(status_msg_id=status_msg.message_id)
    else:
        await message.reply("❌ عدد معتبر وارد کنید (۱ تا ۱۰۰).")

@dp.message(StateFilter(BotStates.QR_N))
async def text_qr(message: Message, state: FSMContext):
    lang = (await state.get_data()).get('lang', 'fa')
    qr = qrcode.QRCode(version=1, box_size=16, border=2)
    qr.add_data(message.text)
    qr.make(fit=True)
    out_io = io.BytesIO()
    qr.make_image(fill_color="#261b23", back_color="#fff").save(out_io, format='PNG')
    out_io.seek(0)
    
    await message.answer_photo(BufferedInputFile(out_io.read(), filename="qr.png"), caption="🔳 بارکد ساخته شد.\n@Ayhan_mojarrad", reply_markup=end_dl_kb(lang))

@dp.message(StateFilter(BotStates.L_PS))
async def text_lock_pdf(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'fa')
    f_path = data.get('tmp_pdf_path')
    password = message.text
    
    wait_msg = await message.reply("🔒 در حال رمزگذاری...")
    anim_task = asyncio.create_task(animated_loading(wait_msg, TEXTS[lang]['processing']))
    
    tmp_out_name = create_safe_temp(".pdf")
    try:
        def run_encryption():
            writer = PdfWriter()
            reader_obx = PdfReader(f_path)
            for page in reader_obx.pages: writer.add_page(page)
            writer.encrypt(password, algorithm="AES-256")
            writer.write(tmp_out_name)
            
        await asyncio.to_thread(run_encryption)
        anim_task.cancel()
        await message.answer_document(FSInputFile(tmp_out_name, filename="@imagerpro_bot.pdf"), caption=f"🔒 فایل شما با رمز <tg-spoiler>{password}</tg-spoiler> قفل شد.\n@Ayhan_mojarrad", parse_mode="HTML", reply_markup=end_dl_kb(lang))
        
    except Exception as e:
        logging.error(f"PDF Lock Error: {e}")
        anim_task.cancel()
        await wait_msg.edit_text(TEXTS[lang]['error'])
    finally:
        if not anim_task.done(): anim_task.cancel()
        if f_path and os.path.exists(f_path): 
            with contextlib.suppress(Exception): os.unlink(f_path)
        if os.path.exists(tmp_out_name): 
            with contextlib.suppress(Exception): os.unlink(tmp_out_name)
        with contextlib.suppress(Exception): await wait_msg.delete()
        await state.clear()

# ==========================================
# سیستم پردازش مدیا و تبدیل فرمت
# ==========================================
@dp.message(F.photo | F.document | F.video | F.audio | F.voice)
async def handle_media(message: Message, state: FSMContext):
    data = await state.get_data()
    current_state = await state.get_state()
    lang = data.get('lang', 'fa')
    if not current_state: return

    # دریافت دقیق آیدی فایل بسته به نوع مدیا
    if message.photo: file_id = message.photo[-1].file_id
    elif message.document: file_id = message.document.file_id
    elif message.video: file_id = message.video.file_id
    elif message.audio: file_id = message.audio.file_id
    else: file_id = message.voice.file_id

    file_info = await bot.get_file(file_id)
    if file_info.file_size > 20 * 1024 * 1024:
        return await message.reply(TEXTS[lang]['size_limit'])

    # 1. UPSCALING IMAGE
    if current_state == BotStates.UP_AI.state:
        wait_msg = await message.reply(f"⏳ دریافت عکس...\n{progress_bar_maker(2, 10)}")
        anim_task = asyncio.create_task(animated_loading(wait_msg, TEXTS[lang]['processing']))
        
        tmp_in_name = create_safe_temp(".jpg")
        tmp_out_name = create_safe_temp(".jpg")

        try:
            await bot.download(file_id, destination=tmp_in_name)
            await asyncio.to_thread(process_ultimate_upscale, tmp_in_name, tmp_out_name)
            anim_task.cancel()
            await message.answer_photo(FSInputFile(tmp_out_name), caption=f"✨ {TEXTS[lang]['success']}\nعکس با موتور هوشمند 4K بازسازی شد.\n@Ayhan_mojarrad", reply_markup=end_dl_kb(lang))
        except Exception as e:
            logging.error(f"Upscale err: {e}")
            anim_task.cancel()
            await wait_msg.edit_text(TEXTS[lang]['error'])
        finally:
            if not anim_task.done(): anim_task.cancel()
            if os.path.exists(tmp_in_name): os.unlink(tmp_in_name)
            if os.path.exists(tmp_out_name): os.unlink(tmp_out_name)
            with contextlib.suppress(Exception): await wait_msg.delete()

    # 2. COMPRESSION OPTIONS
    elif current_state in [BotStates.P_COMP.state, BotStates.VID_C.state, BotStates.AUD_C.state]:
        mb = file_info.file_size / (1024*1024)
        c_type = "P_COMP" if current_state == BotStates.P_COMP.state else ("VID_C" if current_state == BotStates.VID_C.state else "AUD_C")
        await state.update_data(tmp_file_id=file_id, tmp_ctype=c_type)
        await message.reply(f"📊 حجم فعلی: <b>{mb:.2f} MB</b>\n⚙️ لطفاً میزان کاهش را انتخاب کنید:", parse_mode="HTML", reply_markup=universal_comp_kb(lang))

    # 3. EXIF FINDER LOCATOR
    elif current_state == BotStates.EXIF_L.state:
        if message.photo: return await message.reply("❌ لطفاً تصویر را به صورت **فایل (Document)** بفرستید.")
        wait_msg = await message.reply("🔍 در حال جستجوی ماهواره‌ای...")
        anim_task = asyncio.create_task(animated_loading(wait_msg, TEXTS[lang]['processing']))
        
        tmp_name = create_safe_temp()
        try:
            await bot.download(file_id, destination=tmp_name)
            exif_data = Image.open(tmp_name)._getexif()
            gps_coords = None
            if exif_data:
                gps_info = {GPSTAGS.get(t, t): v for t, v in exif_data.get(34853, {}).items()}
                if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
                    calc = lambda x: float(x[0]) + (float(x[1])/60.0) + (float(x[2])/3600.0)
                    lat = calc(gps_info['GPSLatitude']) * (-1 if gps_info.get('GPSLatitudeRef') != 'N' else 1)
                    lon = calc(gps_info['GPSLongitude']) * (-1 if gps_info.get('GPSLongitudeRef') != 'E' else 1)
                    gps_coords = (lat, lon)
            
            anim_task.cancel()
            if gps_coords:
                map_url = f"https://www.google.com/maps?q={gps_coords[0]},{gps_coords[1]}"
                await wait_msg.edit_text(f"✅ نقشه یافت شد:\n<a href='{map_url}'>🌐 مشاهده روی نقشه گوگل</a>", parse_mode="HTML", disable_web_page_preview=False, reply_markup=bck_kb(lang))
            else:
                await wait_msg.edit_text("❌ هیچ موقعیتی (GPS) در این عکس ثبت نشده است.", reply_markup=bck_kb(lang))
        except Exception as e:
            logging.error(f"Exif Error: {e}")
            anim_task.cancel()
            await wait_msg.edit_text(TEXTS[lang]['error'])
        finally:
            if not anim_task.done(): anim_task.cancel()
            if os.path.exists(tmp_name): os.unlink(tmp_name)

    # 4. SCANNER
    elif current_state == BotStates.SCAN_WAIT.state:
        scan_files = data.get('scan_files', [])
        total = data.get('scan_count', 1)
        status_msg_id = data.get('status_msg_id')
        
        tmp_name = create_safe_temp(".jpg")
        await bot.download(file_id, destination=tmp_name)
        scan_files.append(tmp_name)
        await state.update_data(scan_files=scan_files)
        
        count = len(scan_files)
        if count < total:
            bar_dynm_sc = progress_bar_maker(count, total, min(total,12), fill='🟢', empty='⚪️')
            with contextlib.suppress(Exception):
                await bot.edit_message_text(f"📸 <b>در حال دریافت تصاویر...</b>\n\n{bar_dynm_sc}\nدریافت شده: {count} از {total}", chat_id=message.chat.id, message_id=status_msg_id, parse_mode="HTML", reply_markup=bck_kb(lang))
        else:
            with contextlib.suppress(Exception): await bot.delete_message(chat_id=message.chat.id, message_id=status_msg_id)
            
            wait_msg = await message.reply("📑 در حال ساخت فایل PDF...")
            anim_task = asyncio.create_task(animated_loading(wait_msg, TEXTS[lang]['processing']))
            
            def make_pdf():
                images = [ImageEnhance.Contrast(ImageOps.exif_transpose(Image.open(f)).convert("RGB")).enhance(1.4) for f in scan_files]
                out_name = create_safe_temp(".pdf")
                if images: images[0].save(out_name, save_all=True, append_images=images[1:], format="PDF")
                return out_name
            
            try:
                pdf_path = await asyncio.to_thread(make_pdf)
                anim_task.cancel()
                await message.answer_document(FSInputFile(pdf_path, filename="@imagerpro_bot.pdf"), caption=f"✅ {TEXTS[lang]['success']}", reply_markup=end_dl_kb(lang))
            except Exception as e:
                logging.error(f"Scan PDF Error: {e}")
                anim_task.cancel()
                await wait_msg.edit_text(TEXTS[lang]['error'])
            finally:
                if not anim_task.done(): anim_task.cancel()
                for f in scan_files: 
                    if os.path.exists(f): os.unlink(f)
                with contextlib.suppress(Exception): await wait_msg.delete()
                if 'pdf_path' in locals() and os.path.exists(pdf_path): os.unlink(pdf_path)
                await state.clear()

    # 5. LOCK DOCUMENT INIT 
    elif current_state == BotStates.LCK_PDF.state:
        tmp_name = create_safe_temp(".pdf")
        await bot.download(file_id, destination=tmp_name)
        
        if message.photo or not getattr(message.document, 'mime_type', '').startswith("application/pdf"):
            img = Image.open(tmp_name).convert("RGB")
            img.save(tmp_name, format="PDF")
            
        await state.update_data(tmp_pdf_path=tmp_name)
        await state.set_state(BotStates.L_PS)
        await message.reply("🔑 رمز عبور امنیتی خود را بنویسید:", reply_markup=bck_kb(lang))

    # 6. CONVERT FILE EXTENSIONS ENGINE 
    elif current_state == BotStates.FMT_CONV.state:
        fmt = data.get('target_fmt')
        if not fmt: return
        wait_msg = await message.reply("🔄 در حال تغییر فرمت...")
        anim_task = asyncio.create_task(animated_loading(wait_msg, TEXTS[lang]['processing']))
        
        ext_map = {
            'P2W': ('.pdf', '.docx'),
            'W2P': ('.docx', '.pdf'),
            'P2J': ('.png', '.jpg'),
            'J2P': ('.jpg', '.png')
        }
        ext_in, ext_out = ext_map.get(fmt, ('.tmp', '.tmp'))
        
        tmp_in_name = create_safe_temp(ext_in)
        tmp_out_name = create_safe_temp(ext_out)
        
        try:
            await bot.download(file_id, destination=tmp_in_name)
            
            def convert_file():
                if fmt == "P2W":
                    cv = Converter(tmp_in_name)
                    cv.convert(tmp_out_name, start=0, end=None)
                    cv.close()
                elif fmt == "W2P":
                    try:
                        subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', tmp_in_name, '--outdir', os.path.dirname(tmp_out_name)], check=True)
                        base_name = os.path.splitext(os.path.basename(tmp_in_name))[0]
                        gen_pdf = os.path.join(os.path.dirname(tmp_out_name), base_name + '.pdf')
                        if os.path.exists(gen_pdf):
                            shutil.move(gen_pdf, tmp_out_name)
                        else:
                            raise Exception("LibreOffice output not found.")
                    except FileNotFoundError:
                        raise Exception("LIBREOFFICE_MISSING")
                elif fmt == "P2J":
                    img = Image.open(tmp_in_name)
                    if img.mode != 'RGB': img = img.convert('RGB')
                    img.save(tmp_out_name, format="JPEG", quality=100)
                elif fmt == "J2P":
                    img = Image.open(tmp_in_name)
                    img.save(tmp_out_name, format="PNG")
            
            await asyncio.to_thread(convert_file)
            anim_task.cancel()
            
            if not os.path.exists(tmp_out_name) or os.path.getsize(tmp_out_name) == 0:
                raise Exception("Conversion Output Failed")
                
            await message.answer_document(FSInputFile(tmp_out_name, filename=f"@imagerpro_bot{ext_out}"), caption=f"🔄 {TEXTS[lang]['success']}", reply_markup=end_dl_kb(lang))
        
        except Exception as e:
            logging.error(f"Format Conversion Error: {e}")
            anim_task.cancel()
            if "LIBREOFFICE_MISSING" in str(e):
                await wait_msg.edit_text("❌ قابلیت Word به PDF نیازمند نصب بسته LibreOffice روی سرور است.")
            else:
                await wait_msg.edit_text(TEXTS[lang]['error'])
        finally:
            if not anim_task.done(): anim_task.cancel()
            if os.path.exists(tmp_in_name): os.unlink(tmp_in_name)
            if os.path.exists(tmp_out_name): os.unlink(tmp_out_name)
            with contextlib.suppress(Exception): await wait_msg.delete()
            await state.clear() 

@dp.callback_query(F.data.startswith("ucomp_"))
async def process_compress_action(call: CallbackQuery, state: FSMContext):
    s_data = await state.get_data()
    lang = s_data.get('lang', 'fa')
    fid = s_data.get('tmp_file_id')
    ctype = s_data.get('tmp_ctype')
    if not fid: return
    
    percent = int(call.data.split("_")[1])
    wait_msg = await call.message.edit_text("⚙️ در حال فشرده‌سازی...")
    anim_task = asyncio.create_task(animated_loading(wait_msg, TEXTS[lang]['processing']))
    
    ext_out = '.jpg' if ctype=="P_COMP" else ('.mp4' if ctype=="VID_C" else '.mp3')
    
    tmp_in_name = create_safe_temp()
    tmp_out_name = create_safe_temp(ext_out)
    
    try:
        await bot.download(fid, destination=tmp_in_name)
        if ctype == "P_COMP":
            await asyncio.to_thread(compress_image_sync, tmp_in_name, tmp_out_name, percent)
            anim_task.cancel()
            await bot.send_photo(call.message.chat.id, FSInputFile(tmp_out_name), caption=f"✨ {TEXTS[lang]['success']}\n@Ayhan_mojarrad", reply_markup=end_dl_kb(lang))
        else:
            await async_ffmpeg(tmp_in_name, tmp_out_name, ctype, percent)
            anim_task.cancel()
            if ctype == "VID_C":
                await bot.send_video(call.message.chat.id, FSInputFile(tmp_out_name), caption=f"✅ {TEXTS[lang]['success']}\n@Ayhan_mojarrad", reply_markup=end_dl_kb(lang))
            else:
                await bot.send_audio(call.message.chat.id, FSInputFile(tmp_out_name), caption=f"✅ {TEXTS[lang]['success']}\n@Ayhan_mojarrad", reply_markup=end_dl_kb(lang))
    except Exception as e:
        logging.error(f"Compression Error: {e}")
        anim_task.cancel()
        await wait_msg.edit_text(TEXTS[lang]['error'], reply_markup=bck_kb(lang))
    finally:
        if not anim_task.done(): anim_task.cancel()
        if os.path.exists(tmp_in_name): os.unlink(tmp_in_name)
        if os.path.exists(tmp_out_name): os.unlink(tmp_out_name)
        with contextlib.suppress(Exception): await wait_msg.delete()
        
    await state.clear()
    await state.update_data(lang=lang)

# ==========================================
# اجرای ربات
# ==========================================
from aiohttp import web

# تابع پاسخ‌گویی به پینگ‌های سایت UptimeRobot
async def handle_ping(request):
    return web.Response(text="🚀 Bot is alive and running!")

# تابع راه‌اندازی وب‌سرور روی پورت 8080 ریپلیت
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logging.info("🌐 Web Server started on port 8080 for UptimeRobot")
async def main():
    await init_db()
    print("🚀 BOT IS RUNNING WITH ULTIMATE DEFENSIVE MODE ENABLED")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
