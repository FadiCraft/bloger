import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle

# تعريف الثوابت
BLOG_ID = os.getenv('BLOG_ID', 'YOUR_BLOG_ID')  # سيأتي من GitHub Secrets
SCOPES = ['https://www.googleapis.com/auth/blogger']
TOKEN_FILE = 'token.pickle'

def authenticate():
    """المصادقة مع Google API"""
    creds = None
    
    # تحميل token إذا موجود
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # إذا لم تكن هناك بيانات اعتماد صالحة
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # حفظ credentials للمرة القادمة
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def read_posts_from_folder(folder_path='posts'):
    """قراءة المقالات من مجلد posts"""
    posts = []
    
    for filename in os.listdir(folder_path):
        if filename.endswith('.md'):
            filepath = os.path.join(folder_path, filename)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # فصل العنوان عن المحتوى (العنوان في السطر الأول بعد #)
            lines = content.strip().split('\n')
            title = lines[0].replace('#', '').strip() if lines else filename
            body = '\n'.join(lines[1:]) if len(lines) > 1 else content
            
            posts.append({
                'filename': filename,
                'title': title,
                'content': body
            })
    
    return posts

def publish_post(service, blog_id, title, content, labels=None):
    """نشر مقال على Blogger"""
    
    # تحويل Markdown إلى HTML (بسيط - يمكنك استخدام مكتبة better)
    html_content = content.replace('\n', '<br>')
    
    # إنشاء body المنشور
    post_body = {
        'title': title,
        'content': html_content,
        'labels': labels or ['auto-published', 'github'],
        'status': 'DRAFT'  # يمكنك تغييرها إلى 'LIVE' للنشر المباشر
    }
    
    try:
        # إرسال المنشور
        request = service.posts().insert(
            blogId=blog_id,
            body=post_body,
            isDraft=(post_body['status'] == 'DRAFT')
        )
        post = request.execute()
        
        print(f"✅ تم نشر: {title}")
        print(f"   الرابط: {post.get('url', 'غير متاح')}")
        return True
        
    except Exception as e:
        print(f"❌ خطأ في نشر {title}: {str(e)}")
        return False

def main():
    """الدالة الرئيسية"""
    
    # 1. المصادقة
    print("🔐 جارِ المصادقة مع Blogger API...")
    creds = authenticate()
    
    # 2. بناء الخدمة
    service = build('blogger', 'v3', credentials=creds)
    print("✅ تم الاتصال بنجاح")
    
    # 3. قراءة المقالات
    posts = read_posts_from_folder()
    print(f"📄 وجدت {len(posts)} مقالة للنشر")
    
    # 4. نشر المقالات
    for post in posts:
        print(f"\n📝 معالجة: {post['filename']}")
        print(f"   العنوان: {post['title']}")
        
        publish_post(
            service=service,
            blog_id=BLOG_ID,
            title=post['title'],
            content=post['content'],
            labels=['auto-published', 'github-action']
        )

if __name__ == '__main__':
    main()
