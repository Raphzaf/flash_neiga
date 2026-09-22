"""
Tests de la normalisation de l'URL de base de données.

Une URL copiée depuis le tableau de bord d'un hébergeur porte souvent des
paramètres destinés à un autre pilote. psycopg2 ne les tolère pas : il lève
« invalid dsn: invalid connection option » au moment de se connecter, et
l'application ne sert plus rien du tout. Coller l'URL fournie par Supabase
suffisait donc à mettre le site à terre.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import normalize_database_url  # noqa: E402


def test_render_postgres_scheme_is_upgraded():
    """Render fournit `postgres://`, SQLAlchemy attend `postgresql://`."""
    assert normalize_database_url("postgres://u:p@host/db") == "postgresql://u:p@host/db"


def test_supabase_pooler_parameters_are_dropped():
    """`pgbouncer` et `connection_limit` viennent de Prisma : psycopg2 les refuse."""
    url = "postgresql://u:p@aws.pooler.supabase.com:6543/postgres?pgbouncer=true&connection_limit=1"
    assert normalize_database_url(url) == "postgresql://u:p@aws.pooler.supabase.com:6543/postgres"


def test_supported_parameters_are_preserved():
    """`sslmode` est compris par psycopg2 : le retirer casserait la connexion."""
    url = "postgresql://u:p@host/db?sslmode=require&pgbouncer=true"
    assert normalize_database_url(url) == "postgresql://u:p@host/db?sslmode=require"


def test_plain_urls_are_untouched():
    for url in (
        "postgresql://u:p@host/db",
        "postgresql://u:p@host/db?sslmode=require",
    ):
        assert normalize_database_url(url) == url


def test_credentials_with_special_characters_survive():
    """Un mot de passe contenant des caractères encodés ne doit pas être abîmé."""
    url = "postgresql://user:p%40ss%3Aword@host:5432/db?pgbouncer=true"
    assert normalize_database_url(url) == "postgresql://user:p%40ss%3Aword@host:5432/db"


def test_sqlite_urls_are_left_alone():
    """La normalisation ne concerne que PostgreSQL."""
    assert normalize_database_url("sqlite:///./local.db") == "sqlite:///./local.db"
