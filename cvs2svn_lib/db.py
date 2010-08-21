from sqlalchemy import Table, Column, Integer, Text, MetaData, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
#select([func.count(a

Base = declarative_base()


def setupDB(ctx, db_connection_string, echo=False):
    ctx.db_connection_string = db_connection_string
    ctx.engine = create_engine(db_connection_string, echo=echo)
    ctx.Session = sessionmaker(bind=ctx.engine)
    ctx.session = ctx.Session()
    Base.metadata.create_all(ctx.engine)


#class Project(Base):
#
    #__tablename__ = 'projects'
#
    #id = Column(Integer, primary_key=True)
    #cvs_repos_path = Column(Text)
    #cvs_module = Column(Text)
    #project_cvs_repos_path = Column(Text)
#
    #def __init__(self, project_cvs_repos_path, cvs_repos_root, cvs_module):
        #self.project_cvs_repos_path = project_cvs_repos_path
        #self.cvs_repository_root = cvs_repos_root
        #self.cvs_module = cvs_module
#
    #def __repr__(self):
       #return "<Project(%s, '%s', '%s')>" % (self.id,
                                             #self.cvs_repository_root,
                                             #self.cvs_module)
