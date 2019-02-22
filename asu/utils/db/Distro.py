from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey

Base = declarative_base()


class Distro(Base):
    __tablename__ = "distros"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    alias = Column(String)
    latest = Column(String)
    description = Column(String)

    def __repr__(self):
        return "<Distro(distro='%s')>" % (self.name)


class Version(Base):
    __tablename__ = "versions"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    alias = Column(String)
    description = Column(String)
    distro_id = Column(Integer, ForeignKey("distros.id"))

    distro = relationship("Distro", back_populates="distro")

    def __repr__(self):
        return "<Version(distro='%s', version='%s')>" % (
            self.name,
            self.distro,
        )
