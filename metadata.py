from datetime import datetime
from typing import cast
import sqlalchemy
from sqlalchemy.orm.decl_api import declarative_base
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

Base = declarative_base()
class media_table(Base):
    __tablename__ = "medias"
    id: Mapped[int] = mapped_column(sqlalchemy.Integer, primary_key=True)
    media_id: Mapped[int] = mapped_column(sqlalchemy.Integer, unique=True)
    post_id: Mapped[int] = mapped_column(sqlalchemy.Integer, nullable=False)
    link: Mapped[str] = cast(str, mapped_column(sqlalchemy.String))
    directory: Mapped[str] = cast(str, mapped_column(sqlalchemy.String))
    filename: Mapped[str] = cast(str, mapped_column(sqlalchemy.String))
    size: Mapped[int] = cast(int, mapped_column(sqlalchemy.Integer, default=None))
    media_type: Mapped[str] = mapped_column(sqlalchemy.String)
    downloaded: Mapped[bool] = cast(bool, mapped_column(sqlalchemy.Integer, default=0))
    created_at: Mapped[datetime] = cast(datetime, mapped_column(sqlalchemy.TIMESTAMP))

class metadata:
    dbpath = 'metadata.db'
    session: Session
    engine: sqlalchemy.Engine
    table: media_table
    def __init__(self, profilepath: str):
        self.dbpath = profilepath + '/' + self.dbpath

    def openDatabase(self):
        self.engine = sqlalchemy.create_engine("sqlite+pysqlite:///{0}".format(self.dbpath))
        self.session = Session(self.engine)
        self.table = media_table
        Base.metadata.create_all(self.engine)
        # self.session.add(self.table)
        self.session.flush()
        return self.table
    
    def saveLinks(self,mediainfo):
        with self.session as s:
            reg = media_table(
                media_id = mediainfo['media_id'],
                post_id = mediainfo['post_id'],
                link = mediainfo['link'],
                directory = mediainfo['directory'],
                filename = mediainfo['filename'],
                size = mediainfo['size'],
                media_type = mediainfo['media_type'],
                downloaded = mediainfo['downloaded'],
                created_at = mediainfo['created_at']
                )
            s.add(reg)
            s.commit()

    def checkSaved(self,mediainfo):
        stmt = sqlalchemy.select(self.table).filter_by(media_id=mediainfo['media_id'])
        try:
            reg = self.session.execute(stmt).scalar_one()
        except:
            return False
        return reg

    def checkDownloaded(self,mediainfo):
        stmt = sqlalchemy.select(self.table).filter_by(media_id=mediainfo['media_id'])
        try:
            reg = self.session.execute(stmt).scalar_one()
        except:
            return False
        return reg.downloaded
        

    def markDownloaded(self,mediainfo):
        stmt = sqlalchemy.select(self.table).filter_by(media_id=mediainfo['media_id'])
        with self.session as s:
            reg = s.execute(stmt).scalar_one()
            reg.downloaded = True
            reg.size = mediainfo['size']
            reg.created_at = datetime.now()
            s.commit()



