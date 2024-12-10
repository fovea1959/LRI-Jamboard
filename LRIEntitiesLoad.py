import os
import sys

import dateutil.parser

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import DiskTrackerDao
import DiskTrackerEntities
import DiskTrackerDao as Dao

V_ZALMAN = r'[zalman]:'
V_SYNOLOGY1 = r'\\synology1'
V_SYNOLOGY2 = r'\\synology2'
V_WD_BLUE = r'[WD_BLUE]:'
V_WD_BLACK = r'[WD_BLACK]:'
V_WD_WX42D24ML7N4 = r'[WD-WX42D24ML7N4]:'
V_X3250 = r'\\x3250-[1,2]:'
V_VRP_3809 = r'[VRP_3809]:'
V_VRP_3730 = r'[VRP_3730]:'
V_WHIRLPOOL = r'(whirlpool):'

SS_S1_ARCHIVE_R = (V_SYNOLOGY1, r'\archive\r')
SS_S1_HOMES = (V_SYNOLOGY1, r'\homes')
SS_S1_HOUSEHOLD = (V_SYNOLOGY1, r'\household')
SS_S1_MUSIC = (V_SYNOLOGY1, r'\music')
SS_S1_PHOTOS = (V_SYNOLOGY1, r'\photos')

SS_S2_BACKUP_SETS = (V_SYNOLOGY2, r'\backup_sets')
SS_S2_VIDEO = (V_SYNOLOGY2, r'\video')

SS_X3250_IC_TIMELAPSE = (V_X3250, r'\3620-pi-camera-1')

SS_VRP = (V_WHIRLPOOL, r'\VRP')

DD_ZALMAN_R = (V_ZALMAN, r'\r')
DD_ZALMAN_MUSIC = (V_ZALMAN, r'\music'),
DD_WD_BLUE = (V_WD_BLUE, r'\bk_synology1_wd_blue.hbk')
DD_WX42_S1 = (V_WD_WX42D24ML7N4, r'\WD-WX42D24ML7N4_synology1')
DD_WX42_S2 = (V_WD_WX42D24ML7N4, r'\WD-WX42D24ML7N4_synology2')
DD_WD_BLACK = (V_WD_BLACK, r'\bk_video_wd_black')
DD_IC_3809 = (V_VRP_3809, r'\3620-pi-camera-1')
DD_IC_3730 = (V_VRP_3730, r'\3620-pi-camera-1')
DD_VRP_3809 = (V_VRP_3809, r'\VRP')
DD_VRP_3730 = (V_VRP_3730, r'\VRP')

jj = {
    'bkp_synology1_wd_blue': ((SS_S1_HOMES, SS_S1_HOUSEHOLD, SS_S1_PHOTOS), DD_WD_BLUE, 'hyperbackup', (
        ('integrity check', '2024-08-30 16:48'),
        ('backup', '2024-08-30 13:16'),
    ), {}),
    'WD-WX42D24ML7N4_synology1': ((SS_S1_HOMES, SS_S1_HOUSEHOLD, SS_S1_PHOTOS), DD_WX42_S1, 'hyperbackup', (
        ('backup', '2024-08-09 13:55'),
    ), {}),
    'WD-WX42D24ML7N4_synology2': ((SS_S2_BACKUP_SETS, SS_S2_VIDEO), DD_WX42_S2, 'hyperbackup', (
        ('backup', '2024-08-30 11:57'),
    ), {}),
    'bkp_video_wd_black': ((SS_S2_BACKUP_SETS, SS_S2_VIDEO), DD_WD_BLACK, 'hyperbackup', (
        ('backup', '2024-08-30 14:12'),
        ('integrity check', '2020-10-18 13:36'),
    ), {}),
    'desktop/zalman_r': ((SS_S1_ARCHIVE_R, ), DD_ZALMAN_R, 'jfilesync', (
        ('backup', '2024-08-30'),
        ('backup', '2019-07-19 15:22'),
        ('backup', '2019-06-19 15:22'),
    ), {}),
    'ic_to_3809': ((SS_X3250_IC_TIMELAPSE,), DD_IC_3809, 'tar/md5', (
        ('tar/md5', '2024-11-21'),
    ), {}),
    'ic_to_3730': ((SS_X3250_IC_TIMELAPSE,), DD_IC_3730, 'tar/md5', (
        ('tar/md5', '2024-11-21'),
    ), {}),
    'vrp_to_3809': ((SS_VRP,), DD_VRP_3809, 'tar/md5', (
        ('md5', '2024-11-21'),
    ), {}),
    'vrp_to_3730': ((SS_VRP,), DD_VRP_3730, 'tar/md5', (
        ('md5', '2024-11-21'),
    ), {}),
}


def main(argv):
    try:
        os.remove('DiskTracker.db')
    except FileNotFoundError:
        pass
    DiskTrackerEntities.Base.metadata.create_all(DiskTrackerDao.engine)

    vv = set()
    ss = set()
    dd = set()
    for vtuple in jj.values():
        for s1 in vtuple[0]:
            ss.add(s1)
        dd.add(vtuple[1])
    print(ss)
    print(dd)
    for s1 in ss:
        vv.add(s1[0])
    for d1 in dd:
        vv.add(d1[0])
    print(vv)

    with (Session(DiskTrackerDao.engine) as session):

        for v in vv:
            session.add(DiskTrackerEntities.Volume(volume_name=v))
        session.commit()

        for s in ss:
            session.add(DiskTrackerEntities.Source(
                source_volume_id=Dao.volume_by_name(session, s[0]).volume_id,
                source_directory=s[1])
            )

        for d in dd:
            session.add(DiskTrackerEntities.Destination(
                destination_volume_id=Dao.volume_by_name(session, d[0]).volume_id,
                destination_directory=d[1])
            )
        session.commit()

        # add jobs
        for k, vtuple in jj.items():
            job = DiskTrackerEntities.Job(
                job_name=k,
                job_tool=vtuple[2],
                destination=Dao.destination_by_name_tuple(session, vtuple[1]),
                sources=[Dao.source_by_name_tuple(session, s1) for s1 in vtuple[0]]
            )
            session.add(job)
        session.commit()

        # add history
        for k, vtuple in jj.items():
            job = Dao.job_by_name(session, k)
            print('job', job)

            for op, ts in vtuple[3]:
                when = dateutil.parser.parse(ts)
                Dao.record_job(session, job=job, operation=op, when=when, comment="")
        session.commit()


if __name__ == '__main__':
    main(sys.argv[1:])
