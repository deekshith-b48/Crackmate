"""Security talking points for a project. Deterministic: questions come from the stack found in the code, not a model."""

QUESTIONS = {
    "jwt": ["How do you sign and verify tokens, and where is the signing secret stored?", "What happens if a token leaks? How would you revoke it?"],
    "oauth": ["Walk me through the OAuth flow you used. Which grant type and why?", "How do you protect against redirect and CSRF attacks in the flow?"],
    "express": ["How do you validate input and set CORS and security headers in your API?", "Where do rate limits live, and what stops brute-force logins?"],
    "fastapi": ["How do you validate request data and authorise each endpoint?", "How do you handle CORS, and what do you return on errors without leaking internals?"],
    "flask": ["How do you validate input and protect sessions and cookies?"], "django": ["Which of Django's built-in protections (CSRF, ORM, sessions) did you rely on?"],
    "spring": ["How is authentication and authorisation configured in your Spring app?"],
    "postgresql": ["How do you prevent SQL injection in your queries?", "Who can read the database, and how are credentials rotated?"],
    "mysql": ["How do you prevent SQL injection in your queries?"], "sqlite": ["How do you protect the local database file and the data inside it?"],
    "mongodb": ["How do you prevent NoSQL injection, and how is the database exposed to the network?"],
    "redis": ["What stops an outsider reaching your cache, and what sensitive data lives in it?"],
    "docker": ["What is in your image, and does the container run as root?", "How do you keep secrets out of the image and the build history?"],
    "llm": ["How do you keep API keys safe, and how do you defend against prompt injection from user text?"],
    "socket.io": ["How do you authenticate WebSocket connections and stop one user reading another's messages?"],
    "react": ["Where do you keep tokens in the browser, and how do you avoid cross-site scripting?"],
    "react native": ["What do you store on the device, and how is it protected if the phone is lost?"],
}
GENERAL = ["How do you manage secrets and configuration across development and production?", "What would you check first if you suspected your service had been breached?"]
FINDING = "Your repository has a committed secret, so expect: \"Tell me about a time a secret leaked, and how you responded.\""


def questions(technologies, has_secrets):
    """Up to 8 questions: leaked-secret story first when a secret was found, then stack-specific, then general."""
    out = [FINDING] if has_secrets else []
    for tech in technologies:
        out += QUESTIONS.get(tech, [])
    return list(dict.fromkeys(out + GENERAL))[:8]
