# SOS Video Email Setup Guide

## Overview
The SOS feature now automatically records video and sends it via email to all emergency contacts when triggered.

## Features
- ✅ Automatic video recording when SOS is triggered
- ✅ Video size validation (max 25MB for email compatibility)
- ✅ Email sent to all emergency contacts with video attachment
- ✅ Location details included in email
- ✅ Google Maps link for quick navigation

## Email Configuration

### Option 1: Gmail (Recommended for Testing)

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password**:
   - Go to Google Account → Security → 2-Step Verification
   - Scroll to "App passwords"
   - Select "Mail" and "Other (Custom name)"
   - Copy the 16-character password

3. **Update `.env` file**:
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
FROM_EMAIL=your-email@gmail.com
```

### Option 2: Other Email Providers

#### Outlook/Hotmail
```bash
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASSWORD=your-password
FROM_EMAIL=your-email@outlook.com
```

#### Yahoo Mail
```bash
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USER=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@yahoo.com
```

## Video Size Limit

The video is automatically limited to **25MB** to ensure email delivery:
- Most email providers accept attachments up to 25MB
- Videos larger than 25MB will be rejected
- Frontend should compress video before upload

## API Endpoint

### Trigger SOS with Video

**Endpoint**: `POST /api/v1/sos/trigger`

**Content-Type**: `multipart/form-data`

**Parameters**:
- `latitude` (float, required): Current latitude
- `longitude` (float, required): Current longitude
- `video` (file, optional): Video file (max 25MB)

**Example Response**:
```json
{
  "message": "SOS alert sent successfully",
  "contacts_notified": 3,
  "video_attached": true,
  "location": {
    "latitude": 23.8103,
    "longitude": 90.4125
  }
}
```

## Email Template

The email sent to emergency contacts includes:
- 🚨 Emergency alert header
- User's name
- Exact GPS coordinates
- Google Maps link
- Video attachment (if provided)
- Emergency service numbers

## Testing

1. **Configure email settings** in `.env`
2. **Add emergency contacts** with valid email addresses
3. **Trigger SOS** from the app
4. **Check email** in emergency contact's inbox

## Troubleshooting

### Email not sending
- Check SMTP credentials in `.env`
- Verify email provider allows SMTP
- Check firewall/antivirus blocking port 587
- Review backend logs for errors

### Video too large
- Ensure video is under 25MB
- Frontend should compress before upload
- Consider reducing video quality/duration

### Email in spam folder
- Add sender to contacts
- Mark as "Not Spam"
- Use verified domain email

## Security Notes

⚠️ **Important**:
- Never commit `.env` file to git
- Use app-specific passwords, not main account password
- Rotate passwords regularly
- Use environment variables in production

## Production Recommendations

For production deployment:
1. Use a dedicated email service (SendGrid, AWS SES, Mailgun)
2. Implement email queue system
3. Add retry logic for failed sends
4. Monitor email delivery rates
5. Set up SPF/DKIM records for better deliverability
