import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def test_email():
    email_user = os.environ.get("EMAIL_USERNAME")
    email_pass = os.environ.get("EMAIL_PASSWORD")
    
    if not email_user or not email_pass:
        print("❌ Error: EMAIL_USERNAME or EMAIL_PASSWORD environment variables are missing.")
        return
        
    print(f"Attempting to send test email to {email_user}...")
    
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "🛠️ Test Email - Jobs Engine"
        msg["From"] = email_user
        msg["To"] = email_user
        
        body = "If you are reading this, your email configuration works perfectly!"
        msg.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            # Uncomment for detailed SMTP debug logs
            # server.set_debuglevel(1)
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_user, msg.as_string())
            
        print("✅ SUCCESS! Test email sent successfully.")
    except smtplib.SMTPAuthenticationError:
        print("❌ ERROR: Authentication Failed. Did you use an 'App Password' instead of your regular Gmail password? Make sure 2FA is on for your Google account.")
    except Exception as e:
        print(f"❌ ERROR: Failed to send email: {e}")

if __name__ == "__main__":
    test_email()
