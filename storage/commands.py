import sys
from models import Base
from database import engine
# from app import app

def create_tables():
  Base.metadata.create_all(engine)


def drop_tables():
  Base.metadata.drop_all(engine)

# if __name__ == "__main__":
#   if len(sys.argv) > 1 and sys.argv[1] == "drop":
#     drop_tables()

#   create_tables()

#   app.run(port=8090, host="0.0.0.0")