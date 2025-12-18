import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create and return a database connection."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        raise

def fetch_syllabuses():
    """Fetch all syllabuses from the database."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT tm_sb_id as id, tm_sb_name as name FROM tm_syllabus ORDER BY tm_sb_name")
            return cur.fetchall()
    except Exception as e:
        print(f"Error fetching syllabuses: {e}")
        return []
    finally:
        if conn:
            conn.close()

def fetch_standards(syllabus_id):
    """Fetch standards for a given syllabus."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT tm_sd_id as id, tm_sd_name as name 
                FROM tm_standard 
                WHERE tm_sd_syllabus_id = %s 
                ORDER BY tm_sd_name
            """, (syllabus_id,))
            return cur.fetchall()
    except Exception as e:
        print(f"Error fetching standards: {e}")
        return []
    finally:
        if conn:
            conn.close()

def fetch_subjects():
    """Fetch all subjects from the database."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT tm_st_id as id, tm_st_name as name FROM tm_subject ORDER BY tm_st_name")
            return cur.fetchall()
    except Exception as e:
        print(f"Error fetching subjects: {e}")
        return []
    finally:
        if conn:
            conn.close()

def fetch_topics(standard_id, syllabus_id, subject_id):
    """Fetch topics based on standard, syllabus, and subject."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT tm_tp_id as id, tm_tp_name as name 
                FROM tm_topic 
                WHERE tm_tp_standard_id = %s 
                AND tm_tp_syllabus_id = %s 
                AND tm_tp_subject = %s
                ORDER BY tm_tp_name
            """, (standard_id, syllabus_id, subject_id))
            return cur.fetchall()
    except Exception as e:
        print(f"Error fetching topics: {e}")
        return []
    finally:
        if conn:
            conn.close()

def fetch_sections(syllabus_id, standard_id, subject_id, topic_id):
    """Fetch sections based on syllabus, standard, subject, and topic."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT tm_sn_id as id, tm_sn_name as name 
                FROM tm_section 
                WHERE tm_sn_syllabus_id = %s 
                AND tm_sn_standard_id = %s 
                AND tm_sn_subject = %s
                AND tm_sn_topic_id = %s
                ORDER BY tm_sn_name
            """, (syllabus_id, standard_id, subject_id, topic_id))
            return cur.fetchall()
    except Exception as e:
        print(f"Error fetching sections: {e}")
        return []
    finally:
        if conn:
            conn.close()
