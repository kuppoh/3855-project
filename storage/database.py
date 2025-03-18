import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

with open('./config/storage/app_conf.yaml', 'r') as f:
  db_config = yaml.safe_load(f.read())

db_s = db_config['datastore']
engine = create_engine(f"mysql://{db_s['user']}:{db_s['password']}@{db_s['hostname']}:{db_s['port']}/{db_s['db']}")

'''
version: 1
datastore:
  user: keziah
  password: password123
  hostname: localhost
  port: 3306
  db: real_estate

'''

def make_session():
  return sessionmaker(bind=engine)()