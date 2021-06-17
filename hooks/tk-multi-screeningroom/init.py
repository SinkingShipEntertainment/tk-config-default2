# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
import sgtk
import os
import pprint

HookBaseClass = sgtk.get_hook_baseclass()

LOGGER = sgtk.platform.get_logger(__name__)

OCIO_CONFIG = 'X:/tools/aces/aces_1.0.3/config.ocio'

def getRepoPath():
    '''
        quick and dirty for now
    '''
    sgModulePath = sgtk.get_sgtk_module_path()
    sgConfigPath = sgModulePath.replace('\\', '/') 
    parts = sgConfigPath.split('/')[:5]
    sgConfigPath = '/'.join(parts)
    
    # sgConfigPath = 'X:/sgtk_studio/_projects/Magnesium2/shotgun_configuration' # TMP TEST

    LOGGER.debug('sgConfigPath: {0}'.format(sgConfigPath))

    sgConn = sgtk.api.shotgun.connection.get_sg_connection()

    sgFilters = [
        ['code', 'is', 'studio_pipeline'],
        ['id', 'is', 1],
        ['sg_status_list', 'is', 'cmpt']
    ]
    data = sgConn.find_one('CustomNonProjectEntity04', sgFilters, ['sg_repo_major_version', 'sg_repo_minor_version', 'sg_repo_root_path'])
    vMaj = data['sg_repo_major_version']
    vMin = data['sg_repo_minor_version']

    repoPath = None

    parts = sgConfigPath.split('/')    
    parts = parts[4].split('_')

    if len(parts) == 4:
        name = parts[3]
        if name == 'master':
            repoPath = 'X:/tools/pipeline_repos/studio_pipeline_{0}_{1}_dev_master_repo'.format(vMaj, vMin)
        else:
            repoPath = 'X:/dev/ss_dev_{0}/studio_pipeline_{1}_{2}_dev_master_repo'.format(name, vMaj, vMin)
    elif len(parts) == 3:
        repoPath = 'X:/tools/pipeline_repos/studio_pipeline_{0}_{1}_dev_master_repo'.format(vMaj, vMin)
    elif len(parts) == 2:
        repoPath = 'X:/tools/pipeline_repos/studio_pipeline_{0}_{1}_repo'.format(vMaj, vMin)
        
    if not os.path.exists(repoPath):
        LOGGER.warning('repo path: {0} does\'t exist'.format(repoPath))
        return None

    return repoPath



class ScreeningroomInit(HookBaseClass):
    """
    Controls the initialization in and around screening room
    """

    def before_rv_launch(self, path):
        """
        Executed before RV is being launched

        :param path: The path to the RV that is about to be launched
        :type path: str
        """

        # set the OCIO env var
        os.environ['OCIO'] = OCIO_CONFIG
        LOGGER.debug('set OCIO to {}'.format(os.environ['OCIO']))

        # try and find the repo so that we can set RV_SUPPORT_PATH
        repoPath = getRepoPath()
        if not repoPath:
            return
    
        rvPath = repoPath + '/rv'
        if not os.path.exists(rvPath):
            LOGGER.warning('rv support path: {0} does\'t exist'.format(repoPath))
            return

        os.environ['RV_SUPPORT_PATH'] = rvPath
        LOGGER.info('set RV_SUPPORT_PATH to {0}'.format(rvPath))
        
        # raise Exception('testing early return')


