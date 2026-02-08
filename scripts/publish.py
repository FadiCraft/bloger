#!/usr/bin/env python3
"""
سكريبت النشر التلقائي على بلوجر من GitHub Actions
"""

import os
import json
import base64
import pickle
import sys
from datetime import datetime
from pathlib import Path

# مكتبات Google API
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ========== الإعدادات ==========
# هذه تأتي من GitHub Secrets
BLOG_ID = os.environ.get('BLOG_ID', '1234567890123456789')  # استبدل بالرقم الحقيقي للتجربة
SCOPES = ['https://www.googleapis.com/auth/blogger']

# ========== الدوال المساعدة ==========
def setup_client_secret():
    """إنشاء ملف client_secret.json من متغير البيئة"""
    client_secret_json = os.environ.get('CLIENT_SECRET_JSON')
    
    if not client_secret_json:
        print("❌ خطأ: CLIENT_SECRET_JSON غير موجود في متغيرات البيئة")
        print("🔍 تأكد من إضافته في GitHub Secrets")
        sys.exit(1)
    
    try:
        # تحقق من أن JSON صالح
        json.loads(client_secret_json)
        
        # كتابة الملف
        with open('client_secret.json', 'w', encoding='utf-8') as f:
            f.write(client_secret_json)
        
        print("✅ تم إنشاء client_secret.json")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ خطأ في تنسيق CLIENT_SECRET_JSON: {e}")
        sys.exit(1)

def get_credentials():
    """الحصول على بيانات الاعتماد (Credentials)"""
    creds = None
    token_b64 = os.environ.get('TOKEN_PICKLE')
    
    # 1. محاولة تحميل token من GitHub Secrets
    if token_b64 and token_b64 != '':
        try:
            print("🔑 تحميل Token من البيئة...")
            token_data = base64.b64decode(token_b64)
            creds = pickle.loads(token_data)
            print("✅ تم تحميل Token")
        except Exception as e:
            print(f"⚠️ فشل تحميل Token: {e}")
            creds = None
    
    # 2. إذا لم يكن هناك token صالح، إنشاء جديد
    if not creds or not creds.valid:
        print("🔐 إنشاء مصادقة جديدة...")
        
        if creds and creds.expired and creds.refresh_token:
            print("🔄 تجديد Token...")
            creds.refresh(Request())
        else:
            print("🌐 افتح الرابط التالي في المتصفح للمصادقة...")
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', 
                SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # حفظ Token الجديد كـ Base64
        token_pickle = pickle.dumps(creds)
        token_b64_new = base64.b64encode(token_pickle).decode('utf-8')
        
        print("\n" + "="*60)
        print("🚨 **مهم: انسخ هذا الـ Token وأضفه في GitHub Secrets**")
        print("="*60)
        print(f"اسم الـ Secret: TOKEN_PICKLE")
        print(f"القيمة: {token_b64_new[:80]}...")
        print("="*60)
        print("\n1. اذهب إلى GitHub → Settings → Secrets → Actions")
        print("2. New repository secret")
        print("3. Name: TOKEN_PICKLE")
        print("4. Value: الصق الـ Token الكامل")
        print("5. Add secret")
        print("="*60 + "\n")
    
    return creds

def publish_post(service, title, content, labels=None, draft=True):
    """نشر مقال على بلوجر"""
    try:
        post_body = {
            'title': title,
            'content': content,
            'labels': labels or ['github-auto', 'auto-publish'],
        }
        
        print(f"📝 جاري نشر: {title}")
        
        # إرسال المنشور
        request = service.posts().insert(
            blogId=BLOG_ID,
            body=post_body,
            isDraft=draft
        )
        post = request.execute()
        
        print(f"✅ تم النشر بنجاح!")
        print(f"   العنوان: {post.get('title')}")
        print(f"   الرابط: {post.get('url', 'مسودة - لا يوجد رابط')}")
        print(f"   الحالة: {'مسودة' if draft else 'منشور'}")
        print(f"   الوقت: {post.get('published', '')}")
        
        return post
        
    except HttpError as error:
        print(f"❌ خطأ في النشر: {error}")
        return None
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
        return None

def read_posts_from_folder(folder_path='posts'):
    """قراءة المقالات من مجلد posts"""
    posts = []
    
    posts_dir = Path(folder_path)
    
    if not posts_dir.exists():
        print(f"⚠️ مجلد '{folder_path}' غير موجود، جاري إنشاؤه...")
        posts_dir.mkdir()
        return posts
    
    # قراءة جميع ملفات .md
    for md_file in posts_dir.glob('*.md'):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # استخراج العنوان من أول سطر (يبدأ بـ #)
            lines = content.strip().split('\n')
            title = 'مقال بدون عنوان'
            
            if lines and lines[0].startswith('#'):
                title = lines[0].replace('#', '').strip()
                content = '\n'.join(lines[1:])
            else:
                title = md_file.stem.replace('-', ' ').title()
            
            posts.append({
                'file': md_file.name,
                'title': title,
                'content': content,
                'html_content': f"<h1>{title}</h1>\n" + 
                               content.replace('\n', '<br>\n')
            })
            
            print(f"📄 وجدت مقالة: {title}")
            
        except Exception as e:
            print(f"⚠️ خطأ في قراءة {md_file}: {e}")
    
    return posts

def move_published_post(file_path, archive_dir='published'):
    """نقل المقالة المنشورة إلى مجلد الأرشيف"""
    try:
        archive_path = Path(archive_dir)
        if not archive_path.exists():
            archive_path.mkdir()
        
        file = Path(file_path)
        if file.exists():
            destination = archive_path / file.name
            file.rename(destination)
            print(f"📦 نقلت إلى الأرشيف: {file.name}")
            return True
    except Exception as e:
        print(f"⚠️ فشل نقل الملف: {e}")
    
    return False

# ========== الدالة الرئيسية ==========
def main():
    print("🚀 بدء عملية النشر التلقائي على بلوجر")
    print(f"📌 Blog ID: {BLOG_ID}")
    print(f"🕒 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # 1. إعداد ملف client_secret.json
    if not setup_client_secret():
        return
    
    # 2. الحصول على بيانات الاعتماد
    creds = get_credentials()
    if not creds:
        print("❌ فشل في الحصول على بيانات الاعتماد")
        return
    
    # 3. الاتصال بخدمة بلوجر
    try:
        service = build('blogger', 'v3', credentials=creds)
        print("✅ تم الاتصال بخدمة بلوجر بنجاح")
    except Exception as e:
        print(f"❌ فشل الاتصال ببلوجر: {e}")
        return
    
    # 4. قراءة المقالات من مجلد posts
    posts = read_posts_from_folder('posts')
    
    if not posts:
        print("📭 لا توجد مقالات جديدة للنشر")
        
        # نشر مقال تجريبي إذا لم توجد مقالات
        print("\n🔧 نشر مقال تجريبي...")
        test_post = {
            'title': f'اختبار تلقائي - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'content': '''
            <h2>هذا مقال اختباري تلقائي</h2>
            <p>تم النشر تلقائياً عبر GitHub Actions.</p>
            <p>التاريخ: {}</p>
            <p>يمكنك تعديل هذا النص أو إضافة مقالات في مجلد <code>posts</code>.</p>
            '''.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'labels': ['اختبار', 'github-actions', 'أولى']
        }
        
        publish_post(
            service=service,
            title=test_post['title'],
            content=test_post['content'],
            labels=test_post['labels'],
            draft=True  # غير إلى False لنشر مباشر
        )
    else:
        # 5. نشر كل المقالات
        print(f"\n📤 جاري نشر {len(posts)} مقالة...")
        published_count = 0
        
        for post in posts:
            result = publish_post(
                service=service,
                title=post['title'],
                content=post['html_content'],
                labels=['auto-published', 'github'],
                draft=True  # غير إلى False لنشر مباشر
            )
            
            if result:
                published_count += 1
                # نقل المقالة المنشورة إلى الأرشيف
                move_published_post(f"posts/{post['file']}")
        
        print(f"\n📊 النتيجة: نُشر {published_count} من أصل {len(posts)} مقالة")
    
    # 6. التحقق من المنشورات
    try:
        print("\n🔍 جاري التحقق من المنشورات الأخيرة...")
        posts_request = service.posts().list(
            blogId=BLOG_ID,
            maxResults=5
        )
        posts_list = posts_request.execute()
        
        if 'items' in posts_list:
            print(f"📚 آخر {len(posts_list['items'])} منشور في المدونة:")
            for i, post in enumerate(posts_list['items'], 1):
                status = "مسودة" if post.get('status') == 'DRAFT' else "منشور"
                print(f"  {i}. {post['title']} ({status})")
    except Exception as e:
        print(f"⚠️ لا يمكن التحقق من المنشورات: {e}")
    
    print("\n" + "="*50)
    print("🎉 اكتملت العملية بنجاح!")
    print("="*50)

# ========== نقطة الدخول ==========
if __name__ == '__main__':
    main()
