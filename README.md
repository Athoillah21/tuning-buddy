# PostgreSQL Query Tuning Advisor 🚀

AI-powered query optimization tool for PostgreSQL databases. Analyzes your SQL queries, provides optimization recommendations using AI (Gemini/DeepSeek/Groq), and tests them automatically.

## Features

- 🔍 **Query Analysis** - Run EXPLAIN ANALYZE and get detailed execution plans
- 🤖 **AI Recommendations** - Get optimization suggestions from AI (Gemini, DeepSeek, or Groq)
- 🧪 **Automatic Testing** - Test recommendations using temporary tables
- 📊 **Performance Comparison** - Compare execution times before and after optimization
- 🔒 **Secure Connections** - Database credentials are encrypted

## Tech Stack

- **Backend**: Django 4.2
- **Database**: PostgreSQL (Vercel Postgres supported)
- **AI Providers**: Google Gemini, DeepSeek, Groq (with automatic fallback)
- **Deployment**: Vercel (serverless)

## Quick Start (Local Development)

```bash
# Clone the repository
git clone https://github.com/yourusername/tuning-buddy.git
cd tuning-buddy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start development server
python manage.py runserver
```

## Deploy to Vercel

### 1. Prerequisites

- [Vercel Account](https://vercel.com)
- [Vercel CLI](https://vercel.com/cli) installed
- PostgreSQL database (Vercel Postgres or external)

### 2. Set Environment Variables in Vercel

Go to your Vercel project settings → Environment Variables and add:

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | ✅ |
| `DEBUG` | Set to `False` | ✅ |
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `ENCRYPTION_KEY` | Fernet key for encrypting credentials | ✅ |
| `GEMINI_API_KEY` | Google Gemini API key | At least one AI key |
| `DEEPSEEK_API_KEY` | DeepSeek API key | At least one AI key |
| `GROQ_API_KEY` | Groq API key (FREE) | At least one AI key |

### 3. Deploy

```bash
# Login to Vercel
vercel login

# Deploy
vercel --prod
```

### 4. Run Migrations on Production

After deployment, run migrations using Vercel CLI or by adding a build command.

## AI Provider Priority

The app uses AI providers in this order:
1. **Gemini** (Google) - First choice
2. **DeepSeek** - Second choice
3. **Groq** (FREE) - Fallback

If one provider fails (quota exceeded, error), it automatically tries the next one.

## Generate Encryption Key

```python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Generate Secret Key

```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Project Structure

```
tuning-buddy/
├── advisor/                 # Main Django app
│   ├── models.py           # Database models
│   ├── views.py            # View controllers
│   ├── services/           # Business logic
│   │   ├── db_connector.py # PostgreSQL connection handler
│   │   ├── gemini_client.py# AI client (multi-provider)
│   │   ├── optimizer.py    # Query optimization logic
│   │   └── query_analyzer.py# SQL parsing & analysis
│   └── templates/          # HTML templates
├── static/css/             # Stylesheets
├── tuning_buddy/           # Django project settings
├── requirements.txt        # Python dependencies
└── vercel.json            # Vercel config
```

## License

MIT License
