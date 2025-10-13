import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from neo4j import GraphDatabase
from retry import retry
import os
from dotenv import load_dotenv
from utils.helper import create_logger

load_dotenv(".env.dev")


NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
HOSPITALS_CSV_PATH = os.getenv("HOSPITALS_CSV_PATH")
PAYERS_CSV_PATH = os.getenv("PAYERS_CSV_PATH")
PHYSICIANS_CSV_PATH = os.getenv("PHYSICIANS_CSV_PATH")
PATIENTS_CSV_PATH = os.getenv("PATIENTS_CSV_PATH")
VISITS_CSV_PATH = os.getenv("VISITS_CSV_PATH")
REVIEWS_CSV_PATH = os.getenv("REVIEWS_CSV_PATH")

GRAPHDB_NAME = os.getenv("GRAPHDB_NAME")
NODES = ["Hospital", "Payer", "Physician", "Patient", "Visit", "Review"]

logger = create_logger()
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

@retry(tries=5, delay=2)
def check_connection():
  try:
    # verify_connectivity performs a lightweight connection check
    driver.verify_connectivity()
    print("Connected to Neo4j successfully.")
  except Exception as e:
    print(f"Connection failed: {e}")
    raise


def _set_uniqueness_constraints(tx,node):
  query = f"""
  CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node})
  REQUIRE n.id IS UNIQUE;
  """
  _ = tx.run(query, {})


@retry(tries=10, delay=5)
def load_hospital_graph_from_csv() -> None:
  """
  Load structured hospital CSV data into Neo4j following a specific ontology:
  - Only include the id in MERGE.
  - Put all other properties in ON CREATE and ON MATCH.
  """

  # =====================================  LOADING NODES ================================================
  logger.info("Setting uniqueness constraints on nodes") 
  with driver.session(database=GRAPHDB_NAME) as session: 
    for node in NODES: 
      session.execute_write(_set_uniqueness_constraints, node)
  
  logger.info("Loading hospital nodes")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MERGE (h:Hospital {id: toInteger(row.hospital_id)})
      ON CREATE SET 
        h.name = row.hospital_name,
        h.state_name = row.hospital_state
      ON MATCH SET 
        h.name = row.hospital_name,
        h.state_name = row.hospital_state
    """

    _ = session.run(query=query, parameters={"CSV_PATH": HOSPITALS_CSV_PATH})

  logger.info("Loading physician nodes")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MERGE (p:Physician {id: toInteger(row.physician_id)})
      ON CREATE SET 
        p.name = row.physician_name,
        p.school = row.medical_school,
        p.dob = row.physician_dob,
        p.grad_year = row.physician_grad_year,
        p.salary = toFloat(row.salary)
      ON MATCH SET 
        p.name = row.physician_name,
        p.school = row.medical_school,
        p.dob = row.physician_dob,
        p.grad_year = row.physician_grad_year,
        p.salary = toFloat(row.salary)
    """
    _ = session.run(query=query, parameters={"CSV_PATH": PHYSICIANS_CSV_PATH})

  logger.info("Loading patient nodes")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MERGE (p:Patient {id: toInteger(row.patient_id)})
      ON CREATE SET
        p.name = row.patient_name,
        p.blood_type = row.patient_blood_type,
        p.dob = row.patient_dob,
        p.sex = row.patient_sex
    """
    _ = session.run(query=query, parameters={"CSV_PATH": PATIENTS_CSV_PATH})

  logger.info("Loading payer node")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MERGE (p:Payer {id: toInteger(row.payer_id)})
      ON CREATE SET
        p.name = row.payer_name
      ON MATCH SET
        p.name = row.payer_name
    """
    _ = session.run(query=query, parameters={"CSV_PATH": PAYERS_CSV_PATH})
  
  logger.info("Loading visit node")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MERGE (v:Visit {id: toInteger(row.visit_id)})
      ON CREATE SET
        v.admission_date = row.date_of_admission,
        v.admission_type = row.admission_type,
        v.room_number = toInteger(row.room_number),
        v.test_results = row.test_results,
        v.status = row.visit_status,
        v.treatment_description = row.treatment_description,
        v.primary_diagnosis = row.primary_diagnosis,
        v.chief_complaint = row.chief_complaint,
        v.discharge_date = row.discharge_date
      ON MATCH SET
        v.admission_date = row.date_of_admission,
        v.admission_type = row.admission_type,
        v.room_number = toInteger(row.room_number),
        v.test_results = row.test_results,
        v.status = row.visit_status,
        v.treatment_description = row.treatment_description,
        v.primary_diagnosis = row.primary_diagnosis,
        v.chief_complaint = row.chief_complaint,
        v.discharge_date = row.discharge_date
    """
    
    _ = session.run(query=query, parameters={"CSV_PATH": VISITS_CSV_PATH})
  
  logger.info("Loading review node")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MERGE (r:Review {id: toInteger(row.review_id)})
      ON CREATE SET
        r.physician_name = row.physician_name,
        r.hospital_name = row.hospital_name,
        r.patient_name = row.patient_name,
        r.text = row.review
    """
    _ = session.run(query=query, parameters={"CSV_PATH": REVIEWS_CSV_PATH})

  # =====================================  LOADING RELATIONSHIP ================================================
  logger.info("Loading AT relationship")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MATCH (v:Visit {id: toInteger(row.visit_id)})
      MATCH (h:Hospital {id: toInteger(row.hospital_id)})
      MERGE (v)-[at:AT]->(h)
    """
    _ = session.run(query=query, parameters={"CSV_PATH": VISITS_CSV_PATH})

  logger.info("Loading WRITES relationship")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS
      FROM $CSV_PATH AS row
      MATCH (v:Visit {id: toInteger(row.visit_id)})
      MATCH (r:Review {id: toInteger(row.review_id)})
      MERGE (v)-[writes:WRITES]->(r)
    """
    _ = session.run(query=query, parameters={"CSV_PATH": REVIEWS_CSV_PATH})

  logger.info("Loading HAS relationship")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MATCH (p:Patient {id: toInteger(row.patient_id)})
      MATCH (v:Visit {id: toInteger(row.visit_id)})
      MERGE (p)-[has:HAS]->(v)
    """
    _ = session.run(query=query, parameters={"CSV_PATH": VISITS_CSV_PATH})
  
  logger.info("Loading TREATS relationship")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS
      FROM $CSV_PATH AS row 
      MATCH (v:Visit {id: toInteger(row.visit_id)})
      MATCH (p:Physician {id: toInteger(row.physician_id)})
      MERGE (p)-[treats:TREATS]->(v)
    """
    _ = session.run(query=query, parameters={"CSV_PATH": VISITS_CSV_PATH})
  
  logger.info("Loading COVERED_BY relationship")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS
      FROM $CSV_PATH AS row
      MATCH (v:Visit {id: toInteger(row.visit_id)})
      MATCH (p:Payer {id: toInteger(row.payer_id)})
      MERGE (v)-[covered_by:COVERED_BY]->(p)
      ON CREATE SET
        covered_by.billing_amount = toFloat(row.billing_amount),
        covered_by.service_date = row.discharge_date
    """
    _ = session.run(query=query, parameters={"CSV_PATH": VISITS_CSV_PATH})
  
  logger.info("Loading EMPLOYS relationship")
  with driver.session(database=GRAPHDB_NAME) as session: 
    query = """
    LOAD CSV WITH HEADERS 
      FROM $CSV_PATH AS row
      MATCH (h:Hospital {id: toInteger(row.hospital_id)})
      MATCH (p:Physician {id: toInteger(row.physician_id)})
      MERGE (h)-[employs:EMPLOYS]->(p)
    """
    _ = session.run(query=query, parameters={"CSV_PATH": VISITS_CSV_PATH})
  
if __name__ == "__main__": 
  check_connection()
  load_hospital_graph_from_csv()
