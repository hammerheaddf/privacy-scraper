from datetime import datetime
from typing import cast
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.orm.decl_api import declarative_base
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from alembic.autogenerate import produce_migrations
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.operations.ops import ModifyTableOps
from sqlalchemy.exc import OperationalError

Base = declarative_base()
class media_table(Base):
    __tablename__ = "medias"
    id: Mapped[int] = mapped_column(sqlalchemy.Integer, primary_key=True)
    media_id: Mapped[int] = mapped_column(sqlalchemy.Integer, unique=True)
    post_id: Mapped[int] = mapped_column(sqlalchemy.Integer, nullable=False)
    link: Mapped[str] = cast(str, mapped_column(sqlalchemy.String))
    inner_link: Mapped[str] = cast(str, mapped_column(sqlalchemy.String, nullable=True))
    directory: Mapped[str] = cast(str, mapped_column(sqlalchemy.String))
    filename: Mapped[str] = cast(str, mapped_column(sqlalchemy.String))
    size: Mapped[int] = cast(int, mapped_column(sqlalchemy.Integer, default=None))
    media_type: Mapped[str] = mapped_column(sqlalchemy.String)
    downloaded: Mapped[bool] = cast(bool, mapped_column(sqlalchemy.Integer, default=0))
    created_at: Mapped[datetime] = cast(datetime, mapped_column(sqlalchemy.TIMESTAMP))

class post_table(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(sqlalchemy.Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(sqlalchemy.Integer, nullable=False)
    post_text: Mapped[str] = cast(str, mapped_column(sqlalchemy.String))

class metadata:
    dbpath = 'metadata.db'
    session: Session
    engine: sqlalchemy.Engine
    mediatable: media_table
    posttable: post_table
    def __init__(self, profilepath: str):
        self.dbpath = profilepath + '/' + self.dbpath

    def openDatabase(self):
        self.engine = sqlalchemy.create_engine("sqlite+pysqlite:///{0}".format(self.dbpath))
        self.session = Session(self.engine)
        self.upgrade()
        self.mediatable = media_table
        self.posttable = post_table
        Base.metadata.create_all(self.engine)
        # self.session.add(self.mediatable)
        self.session.flush()
        # return self.mediatable
    
    def saveLinks(self,mediainfo):
        with self.session as s:
            reg = media_table(
                media_id = mediainfo['media_id'],
                post_id = mediainfo['post_id'],
                link = mediainfo['link'],
                inner_link = mediainfo['inner_link'],
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
        stmt = sqlalchemy.select(self.mediatable).filter_by(media_id=mediainfo['media_id'])
        try:
            reg = self.session.execute(stmt).scalar_one()
        except:
            return False
        if reg.inner_link == None:
            with self.session as s:
                reg.inner_link = mediainfo['inner_link']
                s.commit()
        return reg

    def checkDownloaded(self,mediainfo):
        stmt = sqlalchemy.select(self.mediatable).filter_by(media_id=mediainfo['media_id'])
        try:
            reg = self.session.execute(stmt).scalar_one()
        except:
            return False
        return reg.downloaded
        

    def markDownloaded(self,mediainfo):
        stmt = sqlalchemy.select(self.mediatable).filter_by(media_id=mediainfo['media_id'])
        with self.session as s:
            reg = s.execute(stmt).scalar_one()
            reg.downloaded = True
            reg.size = mediainfo['size']
            reg.created_at = mediainfo['created_at']
            s.commit()

    def savePost(self,postinfo):
        stmt = sqlalchemy.select(self.posttable).filter_by(post_id=postinfo['post_id'])
        with self.session as s:
            try:
                check = s.execute(stmt).scalar_one()
                if check.post_id == postinfo['post_id']:
                    return True
            except:
                reg = post_table(
                    post_id = postinfo['post_id'],
                    post_text = postinfo['post_text'],
                    )
                s.add(reg)
            s.commit()

    def getMedia(self):
        self.openDatabase()
        stmt = sqlalchemy.select(self.mediatable)
        with self.session as s:
            reg = s.execute(stmt).scalars()
            return reg
        
    def getMediaCount(self):
        self.openDatabase()
        stmt = sqlalchemy.select(sqlalchemy.func.count('*')).select_from(self.mediatable)
        with self.session as s:
            reg = s.execute(stmt).scalar_one()
            return reg

    def getMediaDownloadCount(self):
        self.openDatabase()
        stmt = sqlalchemy.select(sqlalchemy.func.count('*')).select_from(self.mediatable).filter_by(downloaded = False)
        with self.session as s:
            reg = s.execute(stmt).scalar_one()
            return reg

    def getMediaDownload(self):
        self.openDatabase()
        stmt = sqlalchemy.select(self.mediatable).filter_by(downloaded = False)
        with self.session as s:
            reg = s.execute(stmt, execution_options={"prebuffer_rows": True}).scalars()
            return reg

    def upgrade(self):
        try:
            check = self.session.execute(text("select inner_link from medias limit 1"))
        except OperationalError:
            mc = MigrationContext.configure(self.engine.connect())
            migrations = produce_migrations(mc, Base.metadata)
            operations = Operations(mc)
            use_batch = True
            stack = [migrations.upgrade_ops]
            while stack:
                elem = stack.pop(0)
                if use_batch and isinstance(elem, ModifyTableOps):
                    with operations.batch_alter_table(
                        elem.table_name, schema=elem.schema
                    ) as batch_ops:
                        for table_elem in elem.ops:
                            batch_ops.invoke(table_elem)
                elif hasattr(elem, "ops"):
                    stack.extend(elem.ops)
                else:
                    operations.invoke(elem)