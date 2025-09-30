import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from dotenv import load_dotenv
from datetime import datetime
import re

# تحميل المتغيرات من ملف .env
load_dotenv(r"C:\Users\Admin\finance\.env")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# رقم التليجرام المسموح له باستخدام البوت
ALLOWED_USER_ID = 1919573036

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ لم يتم العثور على TELEGRAM_BOT_TOKEN في ملف البيئة")

# حالات المحادثة
ADD_EXPENSE, ADD_INCOME, TRANSFER, NEW_ACCOUNT, CATEGORY, AMOUNT_EXTRACTED, SELECT_ACCOUNT = range(7)
EXCEL_FILE = "financial_tracker.xlsx"

# التحقق من صلاحية المستخدم
def allowed_user_only(func):
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ALLOWED_USER_ID:
            update.message.reply_text("❌ غير مصرح لك باستخدام هذا البوت")
            return ConversationHandler.END
        return func(update, context, *args, **kwargs)
    return wrapper

# دالة محسنة للبحث عن الحسابات
def get_account_name(user_input, accounts_df):
    """
    البحث عن اسم الحساب مع أو بدون الإيموجي - نسخة محسنة
    """
    user_input_clean = re.sub(r'[^\w\s]', '', user_input).strip().lower()
    
    # إذا كان الإدخال رقم فقط، ابحث في الأرقام الموجودة في أسماء الحسابات
    if user_input_clean.isdigit():
        for _, account in accounts_df.iterrows():
            account_name = account['اسم الحساب']
            # البحث عن الأرقام في اسم الحساب
            numbers_in_name = re.findall(r'\d+', account_name)
            if user_input_clean in numbers_in_name:
                return account_name
    
    # البحث الدقيق أولاً
    for _, account in accounts_df.iterrows():
        account_name = account['اسم الحساب']
        account_clean = re.sub(r'[^\w\s]', '', account_name).strip().lower()
        
        # مطابقة تامة أو جزئية
        if user_input_clean == account_clean or user_input_clean in account_clean:
            return account_name
        
        # البحث بأجزاء الاسم
        name_parts = account_clean.split()
        for part in name_parts:
            if user_input_clean == part or user_input_clean in part:
                return account_name
    
    # البحث بالإيموجي إذا لم يتم العثور
    for _, account in accounts_df.iterrows():
        account_name = account['اسم الحساب']
        if user_input.strip() in account_name:
            return account_name
    
    return None

# دالة جديدة لإنشاء قائمة الحسابات بدون إيموجي
def get_accounts_without_emoji(accounts_df):
    """إرجاع قائمة الحسابات بدون إيموجي"""
    accounts_list = []
    for _, acc in accounts_df.iterrows():
        account_name = acc['اسم الحساب']
        # إزالة الإيموجي
        cleaned_name = re.sub(r'[^\w\s]', '', account_name).strip()
        accounts_list.append("• " + cleaned_name)
    return "\n".join(accounts_list)

# استخراج المبلغ من النص - الإصدار المحسن
def extract_amount_from_text(text):
    """
    استخراج المبلغ من النص باستخدام التعابير النمطية المحسنة
    """
    # تحويل الأرقام العربية إلى إنجليزية
    arabic_to_english = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
        '٫': '.', ',': ''
    }
    
    for arabic, english in arabic_to_english.items():
        text = text.replace(arabic, english)
    
    # أنماط للبحث عن المبالغ (محسنة)
    patterns = [
        r'(\d+[\.,]?\d*)\s*(ريال|ر\.س|SAR|ر س|رس)',
        r'(\d+[\.,]?\d*)\s*$',  # مبلغ في نهاية السطر
        r'(\d+[\.,]?\d*)\s',    # مبلغ متبوع بمسافة
        r'(\d+[\.,]?\d*)',      # أي رقم
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # أخذ أول مبلغ موجود
            if isinstance(matches[0], tuple):
                amount_str = matches[0][0]
            else:
                amount_str = matches[0]
            
            # تنظيف المبلغ من الفواصل والنقاط غير الصحيحة
            amount_str = amount_str.replace(',', '').replace(' ', '')
            
            # إذا كان يحتوي على نقطة، تأكد أنها فاصلة عشرية
            if '.' in amount_str:
                parts = amount_str.split('.')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    # هذا مبلغ به سنتات
                    amount_str = parts[0] + '.' + parts[1]
                else:
                    # هذا ربما فاصلة آلاف، نزلها
                    amount_str = amount_str.replace('.', '')
            
            try:
                amount = float(amount_str)
                # إذا كان المبلغ كبير جداً (أكثر من 100,000) ربما يكون خطأ في القراءة
                if amount > 100000:
                    continue
                return amount
            except ValueError:
                continue
    
    # محاولة ثانية للبحث عن أي نمط رقمي
    numbers = re.findall(r'\d+\.?\d*', text)
    if numbers:
        try:
            amount = float(numbers[0].replace(',', ''))
            if amount <= 100000:  # حدود معقولة للمبلغ
                return amount
        except ValueError:
            pass
    
    return None

# تهيئة ملف Excel إذا لم يكن موجوداً
def init_excel_file():
    if not os.path.exists(EXCEL_FILE):
        with pd.ExcelWriter(EXCEL_FILE) as writer:
            accounts_data = {
                'اسم الحساب': ['💳 البنك الأهلي', '💳 بطاقة الائتمان', '💵 النقدي', '📃 ديون على الآخرين'],
                'النوع': ['بنك', 'بطاقة ائتمان', 'نقدي', 'دين'],
                'الرصيد': [10000, 5000, 2000, 3000]
            }
            pd.DataFrame(accounts_data).to_excel(writer, sheet_name='الحسابات', index=False)
            
            expenses_data = {
                'التاريخ': [datetime.now().strftime('%Y-%m-%d')],
                'النوع': ['دخل'],
                'المبلغ': [2000],
                'الحساب': ['💳 البنك الأهلي'],
                'التصنيف': ['💰 راتب']
            }
            pd.DataFrame(expenses_data).to_excel(writer, sheet_name='المعاملات', index=False)
            
            transfers_data = {
                'التاريخ': [datetime.now().strftime('%Y-%m-%d')],
                'من حساب': ['💳 البنك الأهلي'],
                'إلى حساب': ['💵 النقدي'],
                'المبلغ': [1000]
            }
            pd.DataFrame(transfers_data).to_excel(writer, sheet_name='التحويلات', index=False)

def load_data():
    accounts = pd.read_excel(EXCEL_FILE, sheet_name='الحسابات')
    transactions = pd.read_excel(EXCEL_FILE, sheet_name='المعاملات')
    transfers = pd.read_excel(EXCEL_FILE, sheet_name='التحويلات')
    return accounts, transactions, transfers

def save_data(accounts, transactions, transfers):
    with pd.ExcelWriter(EXCEL_FILE) as writer:
        accounts.to_excel(writer, sheet_name='الحسابات', index=False)
        transactions.to_excel(writer, sheet_name='المعاملات', index=False)
        transfers.to_excel(writer, sheet_name='التحويلات', index=False)

# لوحة المفاتيح الرئيسية
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ['➕ إضافة مصروف', '💸 إضافة دخل'], 
        ['🔄 تحويل بين الحسابات', '📊 عرض الحسابات'], 
        ['📈 عرض المصروفات', '🏦 إضافة حساب جديد'],
        ['📋 كشف حساب', '📝 لصق نص للمعالجة']
    ], resize_keyboard=True)

# لوحة المفاتيح لأنواع المعاملات
def get_transaction_type_keyboard():
    return ReplyKeyboardMarkup([
        ['💸 مصروف', '💰 دخل'],
        ['🔙 رجوع للقائمة الرئيسية']
    ], resize_keyboard=True)

# أوامر البوت
@allowed_user_only
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        '👋 مرحباً! أنا بوت إدارة الحسابات الشخصية. \n\n'
        '📌 يمكنني مساعدتك في:\n'
        '• تسجيل المصروفات والدخل 💰\n'
        '• تحويل الأموال بين الحسابات 🔄\n'
        '• متابعة أرصدة حساباتك 📊\n'
        '• إنشاء تقارير مالية 📈\n\n'
        'اختر من الخيارات في لوحة المفاتيح: 👇', 
        reply_markup=get_main_keyboard()
    )

@allowed_user_only
def show_accounts(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    message = "💼 *حساباتك:*\n\n"
    total_balance = 0
    
    for _, account in accounts.iterrows():
        balance = account['الرصيد']
        original_account_name = account['اسم الحساب']
        
        # تنظيف اسم الحساب من الإيموجي
        cleaned_account_name = re.sub(r'[^\w\s]', '', original_account_name).strip()
        
        formatted_balance = "{:,.2f}".format(balance).replace(",", "٬")
        
        # استخدام الإيموجي الأصلي من اسم الحساب
        emoji_match = re.search(r'[^\w\s]', original_account_name)
        emoji = emoji_match.group(0) + " " if emoji_match else "💵 "
        
        # إضافة السطر إلى الرسالة
        message += f"{emoji}*{cleaned_account_name}: {formatted_balance} ريال*\n"
        total_balance += balance
    
    # تنسيق الرصيد الإجمالي
    formatted_total = "{:,.2f}".format(total_balance).replace(",", "٬")
    message += f"\n💰 *الإجمالي: {formatted_total} ريال*"
    
    update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

@allowed_user_only
def show_expenses(update: Update, context: CallbackContext):
    _, transactions, _ = load_data()
    
    if transactions.empty:
        update.message.reply_text("📭 لا توجد معاملات مسجلة بعد.", reply_markup=get_main_keyboard())
        return
    
    recent_transactions = transactions.tail(5)
    message = "📋 **آخر المعاملات:**\n\n"
    
    for _, transaction in recent_transactions.iterrows():
        emoji = "↗️" if transaction['النوع'] == 'مصروف' else "↙️"
        message += f"{emoji} {transaction['التاريخ']} - {transaction['التصنيف']}: {transaction['المبلغ']} ريال\n"
        message += f"   ({transaction['الحساب']})\n\n"  # تم التصحيح هنا
    
    update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

@allowed_user_only
def add_expense(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # عرض الحسابات بدون الإيموجي للمستخدم
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "💸 **إضافة مصروف جديد:**\n\n"
        "أدخل البيانات بالصيغة التالية:\n"
        "`التصنيف, المبلغ, اسم الحساب`\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
        "**أمثلة:**\n"
        "• `طعام, 50, النقدي`\n"
        "• `مواصلات, 30, البنك الأهلي`",
        parse_mode='Markdown'
    )
    return ADD_EXPENSE

@allowed_user_only
def add_income(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # عرض الحsابات بدون الإيموجي للمستخدم
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "💰 **إضافة دخل جديد:**\n\n"
        "أدخل البيانات بالصيغة التالية:\n"
        "`المصدر, المبلغ, اسم الحساب`\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
        "**أمثلة:**\n"
        "• `راتب, 5000, البنك الأهلي`\n"
        "• `عمل حر, 300, النقدي`",
        parse_mode='Markdown'
    )
    return ADD_INCOME

@allowed_user_only
def transfer_money(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # عرض الحسابات بدون الإيموجي للمستخدم
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "🔄 **تحويل بين الحسابات:**\n\n"
        "أدخل البيانات بالصيغة التالية:\n"
        "`من حساب, إلى حساب, المبلغ`\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
        "**مثال:**\n"
        "`البنك الأهلي, النقدي, 1000`",
        parse_mode='Markdown'
    )
    return TRANSFER

@allowed_user_only
def handle_add_expense(update: Update, context: CallbackContext):
    try:
        if update.message.text == '🔙 رجوع للقائمة الرئيسية':
            update.message.reply_text("❌ تم الإلغاء.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
            
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: التصنيف, المبلغ, الحساب")
            return ADD_EXPENSE
            
        category = data[0].strip()
        amount = float(data[1].strip())
        account_input = data[2].strip()
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن اسم الحساب باستخدام الدالة الجديدة
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return ADD_EXPENSE
        
        # تحديث رصيد الحساب
        account_index = accounts[accounts['اسم الحساب'] == account_name].index
        accounts.at[account_index[0], 'الرصيد'] -= amount
        new_balance = accounts.at[account_index[0], 'الرصيد']
        
        # إضافة المعاملة
        new_transaction = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'النوع': 'مصروف',
            'المبلغ': amount,
            'الحساب': account_name,
            'التصنيف': category
        }
        transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        update.message.reply_text(
            f"✅ تم تسجيل مصروف {amount} ريال من {account_name} للتصنيف {category}\n"
            f"📊 الرصيد الحالي: {new_balance:,.2f} ريال",
            reply_markup=get_main_keyboard()
        )
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
        return ADD_EXPENSE
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

@allowed_user_only
def handle_add_income(update: Update, context: CallbackContext):
    try:
        if update.message.text == '🔙 رجوع للقائمة الرئيسية':
            update.message.reply_text("❌ تم الإلغاء.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
            
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: المصدر, المبلغ, الحساب")
            return ADD_INCOME
            
        source = data[0].strip()
        amount = float(data[1].strip())
        account_input = data[2].strip()
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن اسم الحساب باستخدام الدالة الجديدة
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return ADD_INCOME
        
        # تحديث رصيد الحساب
        account_index = accounts[accounts['اسم الحساب'] == account_name].index
        accounts.at[account_index[0], 'الرصيد'] += amount
        new_balance = accounts.at[account_index[0], 'الرصيد']
        
        # إضافة المعاملة
        new_transaction = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'النوع': 'دخل',
            'المبلغ': amount,
            'الحساب': account_name,
            'التصنيف': source
        }
        transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        update.message.reply_text(
            f"✅ تم تسجيل دخل {amount} ريال إلى {account_name} من {source}\n"
            f"📊 الرصيد الحالي: {new_balance:,.2f} ريال",
            reply_markup=get_main_keyboard()
        )
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
        return ADD_INCOME
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

@allowed_user_only
def handle_transfer(update: Update, context: CallbackContext):
    try:
        if update.message.text == '🔙 رجوع للقائمة الرئيسية':
            update.message.reply_text("❌ تم الإلغاء.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
            
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: من حساب, إلى حساب, المبلغ")
            return TRANSFER
            
        from_acc_input = data[0].strip()
        to_acc_input = data[1].strip()
        amount = float(data[2].strip())
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن أسماء الحسابات باستخدام الدالة الجديدة
        from_acc = get_account_name(from_acc_input, accounts)
        to_acc = get_account_name(to_acc_input, accounts)
        
        if not from_acc or not to_acc:
            update.message.reply_text("❌ أحد الحسابات غير موجود!")
            return TRANSFER
        
        # التحقق من الرصيد الكافي
        from_index = accounts[accounts['اسم الحساب'] == from_acc].index
        if accounts.at[from_index[0], 'الرصيد'] < amount:
            update.message.reply_text("❌ الرصيد غير كافي!")
            return TRANSFER
        
        # إجراء التحويل
        accounts.at[from_index[0], 'الرصيد'] -= amount
        to_index = accounts[accounts['اسم الحساب'] == to_acc].index
        accounts.at[to_index[0], 'الرصيد'] += amount
        
        # تسجيل التحويل
        new_transfer = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'من حساب': from_acc,
            'إلى حساب': to_acc,
            'المبلغ': amount
        }
        transfers = pd.concat([transfers, pd.DataFrame([new_transfer])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        update.message.reply_text(f"✅ تم تحويل {amount} ريال من {from_acc} إلى {to_acc}", reply_markup=get_main_keyboard())
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
        return TRANSFER
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

@allowed_user_only
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ تم الإلغاء.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

@allowed_user_only
def handle_message(update: Update, context: CallbackContext):
    text = update.message.text
    if text == '📊 عرض الحسابات':
        show_accounts(update, context)
    elif text == '📈 عرض المصروفات':
        show_expenses(update, context)
    elif text == '🏦 إضافة حساب جديد':
        add_new_account(update, context)
    elif text == '📝 لصق نص للمعالجة':
        handle_paste_text(update, context)
    elif text == '🔙 رجوع للقائمة الرئيسية':
        start(update, context)
    else:
        update.message.reply_text("👋 استخدم الأزرار في لوحة المفاتيح للتفاعل مع البوت", reply_markup=get_main_keyboard())

@allowed_user_only
def add_new_account(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🏦 **إضافة حساب جديد:**\n\n"
        "أدخل بيانات الحساب بالصيغة التالية:\n"
        "`اسم الحساب, النوع, الرصيد الأولي`\n\n"
        "📋 **أنواع الحسابات المتاحة:**\n"
        "• `بنك` - للحسابات البنكية 🏛\n"
        "• `بطاقة ائتمان` - للبطاقات الائتمانية 💳\n" 
        "• `نقدي` - للنقود والسواق 💵\n"
        "• `دين` - للديون والمستحقات 📃\n"
        "• `أشخاص` - للأشخاص 👤\n\n"
        "**أمثلة:**\n"
        "• `بنك الرياض, بنك, 5000`\n"
        "• `بطاقة الائتمان, بطاقة ائتمان, -1000`\n"
        "• `أخي أحمد, أشخاص, 2000`",
        parse_mode='Markdown'
    )
    return NEW_ACCOUNT

@allowed_user_only
def handle_new_account(update: Update, context: CallbackContext):
    try:
        if update.message.text == '🔙 رجوع للقائمة الرئيسية':
            update.message.reply_text("❌ تم الإلغاء.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
            
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: اسم الحساب, النوع, الرصيد")
            return NEW_ACCOUNT
            
        account_name = data[0].strip()
        account_type = data[1].strip()
        initial_balance = float(data[2].strip())
        
        accounts, transactions, transfers = load_data()
        
        # التحقق من عدم وجود حساب بنفس الاسم
        if account_name in accounts['اسم الحساب'].values:
            update.message.reply_text("❌ يوجد حساب بنفس الاسم مسبقاً!")
            return NEW_ACCOUNT
        
        # إضافة الحساب الجديد
        new_account = {
            'اسم الحساب': account_name,
            'النوع': account_type,
            'الرصيد': initial_balance
        }
        
        accounts = pd.concat([accounts, pd.DataFrame([new_account])], ignore_index=True)
        save_data(accounts, transactions, transfers)
        
        update.message.reply_text(
            f"✅ تم إضافة الحساب الجديد بنجاح!\n\n"
            f"🏦 **الحساب:** {account_name}\n"
            f"📋 **النوع:** {account_type}\n"
            f"💵 **الرصيد الأولي:** {initial_balance:,.2f} ريال",
            reply_markup=get_main_keyboard()
        )
        
    except ValueError:
        update.message.reply_text("❌ الرصيد يجب أن يكون رقماً!")
        return NEW_ACCOUNT
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

@allowed_user_only
def account_statement(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "📋 **كشف حساب:**\n\n"
        "أدخل اسم الحساب الذي تريد كشف حسابه:\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}",
        parse_mode='Markdown'
    )
    return CATEGORY

def handle_account_statement(update: Update, context: CallbackContext):
    try:
        account_input = update.message.text.strip()
        accounts, transactions, transfers = load_data()
        
        # البحث عن اسم الحساب
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return ConversationHandler.END
        
        # تنظيف اسم الحساب من الإيموجي للعرض
        cleaned_account_name = re.sub(r'[^\w\s]', '', account_name).strip()
        
        # الحصول على معلومات الحساب
        account_info = accounts[accounts['اسم الحساب'] == account_name].iloc[0]
        current_balance = account_info['الرصيد']
        account_type = account_info['النوع']
        
        # تصفية المعاملات والتحويلات
        account_transactions = transactions[transactions['الحساب'] == account_name]
        outgoing_transfers = transfers[transfers['من حساب'] == account_name]
        incoming_transfers = transfers[transfers['إلى حساب'] == account_name]
        
        # حساب الرصيد الافتتاحي (مجموع الدخل - المصروفات + التحويلات الواردة - الصادرة)
        total_income = account_transactions[account_transactions['النوع'] == 'دخل']['المبلغ'].sum()
        total_expenses = account_transactions[account_transactions['النوع'] == 'مصروف']['المبلغ'].sum()
        total_incoming_transfers = incoming_transfers['المبلغ'].sum()
        total_outgoing_transfers = outgoing_transfers['المبلغ'].sum()
        
        opening_balance = current_balance + total_expenses - total_income + total_outgoing_transfers - total_incoming_transfers
        
        # إنشاء تقرير منظم
        message = f"📊 *كشف حساب: {cleaned_account_name}*\n"
        message += f"📋 النوع: {account_type}\n"
        message += f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d')}\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        message += f"💰 *الرصيد الافتتاحي:* {opening_balance:,.0f} ريال\n\n"
        
        # المعاملات
        message += "💳 *المعاملات*\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        if account_transactions.empty:
            message += "لا توجد معاملات\n\n"
        else:
            # الدخل
            income_transactions = account_transactions[account_transactions['النوع'] == 'دخل']
            if not income_transactions.empty:
                message += "↙️ *الدخل:*\n"
                for _, transaction in income_transactions.iterrows():
                    message += f"   + {transaction['المبلغ']:,.0f} ريال - {transaction['التصنيف']} ({transaction['التاريخ']})\n"
                message += f"   المجموع: +{income_transactions['المبلغ'].sum():,.0f} ريال\n\n"
            
            # المصروفات
            expense_transactions = account_transactions[account_transactions['النوع'] == 'مصروف']
            if not expense_transactions.empty:
                message += "↗️ *المصروفات:*\n"
                for _, transaction in expense_transactions.iterrows():
                    message += f"   - {transaction['المبلغ']:,.0f} ريال - {transaction['التصنيف']} ({transaction['التاريخ']})\n"
                message += f"   المجموع: -{expense_transactions['المبلغ'].sum():,.0f} ريال\n\n"
        
        # التحويلات
        message += "🔄 *التحويلات*\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        if outgoing_transfers.empty and incoming_transfers.empty:
            message += "لا توجد تحويلات\n\n"
        else:
            # التحويلات الواردة
            if not incoming_transfers.empty:
                message += "⬅️ *التحويلات الواردة:*\n"
                for _, transfer in incoming_transfers.iterrows():
                    from_acc_clean = re.sub(r'[^\w\s]', '', transfer['من حساب']).strip()
                    message += f"   + {transfer['المبلغ']:,.0f} ريال من {from_acc_clean} ({transfer['التاريخ']})\n"
                message += f"   المجموع: +{incoming_transfers['المبلغ'].sum():,.0f} ريال\n\n"
            
            # التحويلات الصادرة
            if not outgoing_transfers.empty:
                message += "➡️ *التحويلات الصادرة:*\n"
                for _, transfer in outgoing_transfers.iterrows():
                    to_acc_clean = re.sub(r'[^\w\s]', '', transfer['إلى حساب']).strip()
                    message += f"   - {transfer['المبلغ']:,.0f} ريال إلى {to_acc_clean} ({transfer['التاريخ']})\n"
                message += f"   المجموع: -{outgoing_transfers['المبلغ'].sum():,.0f} ريال\n\n"
        
        # الملخص المالي
        message += "🧮 *الملخص المالي*\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        message += f"الرصيد الافتتاحي: {opening_balance:,.0f} ريال\n"
        message += f"إجمالي الدخل: +{total_income:,.0f} ريال\n"
        message += f"إجمالي المصروفات: -{total_expenses:,.0f} ريال\n"
        message += f"صافي التحويلات: {total_incoming_transfers - total_outgoing_transfers:+,.0f} ريال\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        message += f"💰 *الرصيد الختامي: {current_balance:,.0f} ريال*"
        
        update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return ConversationHandler.END






# دالة جديدة لمعالجة النص الملصق
@allowed_user_only
def handle_paste_text(update: Update, context: CallbackContext):
    update.message.reply_text(
        "📝 **لصق النص للمعالجة:**\n\n"
        "الصق النص الذي يحتوي على المبلغ الذي تريد تسجيله:\n\n"
        "📌 **أمثلة للنصوص التي يمكن معالجتها:**\n"
        "• \"فاتورة سوبرماركت بقيمة 150 ريال\"\n"
        "• \"دفعت 75.5 ريال للبنزين\"\n"
        "• \"راتب 5000 ريال\"\n"
        "• \"مبلغ ٢٥٠ ر.س للعشاء\"\n"
        "• \"29.5 SAR\"\n"
        "• \"بـ:29.5 SAR\"",
        parse_mode='Markdown'
    )
    return AMOUNT_EXTRACTED

# معالجة النص الملصق واستخراج المبلغ
@allowed_user_only
def handle_text_paste(update: Update, context: CallbackContext):
    try:
        if update.message.text == '🔙 رجوع للقائمة الرئيسية':
            update.message.reply_text("❌ تم الإلغاء.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
            
        text = update.message.text
        amount = extract_amount_from_text(text)
        
        if amount is None:
            update.message.reply_text("❌ لم يتم العثور على مبلغ في النص. حاول مرة أخرى.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
        
        # حفظ المبلغ في context للمراحل القادمة
        context.user_data['extracted_amount'] = amount
        context.user_data['transaction_text'] = text
        
        update.message.reply_text(
            f"✅ تم استخراج المبلغ: {amount:,.2f} ريال\n\n"
            "اختر نوع المعاملة:",
            reply_markup=get_transaction_type_keyboard()
        )
        
        return SELECT_ACCOUNT
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ في معالجة النص: {str(e)}", reply_markup=get_main_keyboard())
        return ConversationHandler.END

# معالجة اختيار نوع المعاملة وعرض الحسابات المناسبة
@allowed_user_only
def handle_transaction_type_selection(update: Update, context: CallbackContext):
    try:
        if update.message.text == '🔙 رجوع للقائمة الرئيسية':
            update.message.reply_text("❌ تم الإلغاء.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
            
        transaction_type = update.message.text
        amount = context.user_data.get('extracted_amount')
        original_text = context.user_data.get('transaction_text', '')
        
        if not amount:
            update.message.reply_text("❌ لم يتم العثور على المبلغ. حاول مرة أخرى.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
        
        # تحديد نوع الحسابات المناسبة بناءً على نوع المعاملة
        accounts, _, _ = load_data()
        
        if 'مصروف' in transaction_type:
            # فلترة الحسابات حسب النوع (بطاقة ائتمان، بنك، نقدي)
            suitable_accounts = accounts[accounts['النوع'].isin(['بطاقة ائتمان', 'بنك', 'نقدي'])]
            transaction_kind = 'مصروف'
        else:
            # فلترة الحسابات حسب النوع (بنك، نقدي) للإيرادات
            suitable_accounts = accounts[accounts['النوع'].isin(['بنك', 'نقدي'])]
            transaction_kind = 'دخل'
        
        if suitable_accounts.empty:
            update.message.reply_text("❌ لا توجد حسابات مناسبة متاحة.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
        
        # حفظ نوع المعاملة للمرحلة القادمة
        context.user_data['transaction_kind'] = transaction_kind
        
        # إنشاء أزرار للحسابات المناسبة
        keyboard = []
        account_mapping = {}
        
        for _, account in suitable_accounts.iterrows():
            account_name = account['اسم الحساب']
            # تنظيف اسم الحساب من الإيموجي للعرض
            cleaned_name = re.sub(r'[^\w\s]', '', account_name).strip()
            display_name = f"🏦 {cleaned_name}"
            keyboard.append([display_name])
            account_mapping[display_name] = account_name
        
        # إضافة زر الرجوع
        keyboard.append(['🔙 رجوع للقائمة الرئيسية'])
        
        context.user_data['account_mapping'] = account_mapping
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        update.message.reply_text(
            f"💵 المبلغ: {amount:,.2f} ريال\n"
            f"📋 النوع: {transaction_kind}\n\n"
            "اختر الحساب:",
            reply_markup=reply_markup
        )
        
        return CATEGORY
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}", reply_markup=get_main_keyboard())
        return ConversationHandler.END

@allowed_user_only
def handle_account_selection_for_paste(update: Update, context: CallbackContext):
    try:
        if update.message.text == '🔙 رجوع للقائمة الرئيسية':
            update.message.reply_text("❌ تم الإلغاء.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
            
        selected_account_text = update.message.text
        amount = context.user_data.get('extracted_amount')
        transaction_kind = context.user_data.get('transaction_kind')
        original_text = context.user_data.get('transaction_text', '')
        account_mapping = context.user_data.get('account_mapping', {})
        
        accounts, transactions, transfers = load_data()
        
        # الحصول على اسم الحساب الكامل من الـ mapping
        account_name = account_mapping.get(selected_account_text)
        
        if not account_name:
            # إذا لم يكن في mapping، حاول البحث باستخدام الدالة العادية
            selected_account = selected_account_text.replace("🏦 ", "").strip()
            account_name = get_account_name(selected_account, accounts)
        
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!", reply_markup=get_main_keyboard())
            return ConversationHandler.END
        
        # استخدام النص الأصلي كتصنيف
        category = original_text[:50]
        
        if transaction_kind == 'مصروف':
            account_index = accounts[accounts['اسم الحساب'] == account_name].index
            accounts.at[account_index[0], 'الرصيد'] -= amount
            new_balance = accounts.at[account_index[0], 'الرصيد']
            
            new_transaction = {
                'التاريخ': datetime.now().strftime('%Y-%m-%d'),
                'النوع': 'مصروف',
                'المبلغ': amount,
                'الحساب': account_name,
                'التصنيف': category
            }
        else:
            account_index = accounts[accounts['اسم الحساب'] == account_name].index
            accounts.at[account_index[0], 'الرصيد'] += amount
            new_balance = accounts.at[account_index[0], 'الرصيد']
            
            new_transaction = {
                'التاريخ': datetime.now().strftime('%Y-%m-%d'),
                'النوع': 'دخل',
                'المبلغ': amount,
                'الحساب': account_name,
                'التصنيف': category
            }
        
        transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
        save_data(accounts, transactions, transfers)
        
        cleaned_account_name = re.sub(r'[^\w\s]', '', account_name).strip()
        
        update.message.reply_text(
            f"✅ تم تسجيل {transaction_kind} بنجاح!\n\n"
            f"💵 المبلغ: {amount:,.2f} ريال\n"
            f"📋 النوع: {transaction_kind}\n"
            f"🏦 الحساب: {cleaned_account_name}\n"
            f"📝 التصنيف: {category}\n"
            f"📊 الرصيد الجديد: {new_balance:,.2f} ريال",
            reply_markup=get_main_keyboard()
        )
        
        context.user_data.clear()
            
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}", reply_markup=get_main_keyboard())
    
    return ConversationHandler.END

def main():
    init_excel_file()
    
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex('^➕ إضافة مصروف$'), add_expense),
            MessageHandler(Filters.regex('^💸 إضافة دخل$'), add_income),
            MessageHandler(Filters.regex('^🔄 تحويل بين الحسابات$'), transfer_money),
            MessageHandler(Filters.regex('^🏦 إضافة حساب جديد$'), add_new_account),
            MessageHandler(Filters.regex('^📋 كشف حساب$'), account_statement),
            MessageHandler(Filters.regex('^📝 لصق نص للمعالجة$'), handle_paste_text)
        ],
        states={
            ADD_EXPENSE: [MessageHandler(Filters.text & ~Filters.command, handle_add_expense)],
            ADD_INCOME: [MessageHandler(Filters.text & ~Filters.command, handle_add_income)],
            TRANSFER: [MessageHandler(Filters.text & ~Filters.command, handle_transfer)],
            NEW_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_new_account)],
            CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_account_statement)],
            AMOUNT_EXTRACTED: [MessageHandler(Filters.text & ~Filters.command, handle_text_paste)],
            SELECT_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_transaction_type_selection)],
            CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_account_selection_for_paste)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("cancel", cancel))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    print("🤖 البوت يعمل...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()