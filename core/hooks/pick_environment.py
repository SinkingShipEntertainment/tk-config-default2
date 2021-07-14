# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook which chooses an environment file to use based on the current context.
"""

from tank import Hook


class PickEnvironment(Hook):
    def execute(self, context, **kwargs):
        """
        The default implementation assumes there are three environments, called
        shot, asset and project, and switches to these based on entity type.
        """
        # --- Sanity check, output to see if this method is being called every
        # --- time, and also as a marker to check the output line immediately
        # --- below it in the SG logs to see that the correct env '.yml' file
        # --- is being loaded (uncomment when troubleshooting).
        # --- SSE -DW 2020-04-09
        # title = '===== PickEnvironment().execute()'       #  keep these lines
        # emph = '=' * len(title)                           #  keep these lines
        # t_block = '\n'.join([emph, title, emph, '\n'])    #  keep these lines
        # print(t_block)                                    #  keep these lines

        if context.source_entity:
            if context.source_entity["type"] == "Version":
                return "version"
            elif context.source_entity["type"] == "PublishedFile":
                return "publishedfile"
            elif context.source_entity["type"] == "Playlist":
                return "playlist"

        if context.project is None:
            # Our context is completely empty. We're going into the site
            # context.
            return "site"

        if context.entity is None:
            # We have a project but not an entity.
            return "project"

        if context.entity and context.step is None:
            # We have an entity but no step.
            if context.entity["type"] == "Shot":
                return "shot"
            if context.entity["type"] == "Asset":
                return "asset"
            if context.entity["type"] == "Sequence":
                return "sequence"

        if context.entity and context.step:
            # We have a step and an entity.
            if context.entity["type"] == "Shot":
                return "shot_step"
            if context.entity["type"] == "Asset":
                # return "asset_step"
                # --- Using a custom Step .yml for Surfacing
                # --- to allow for filename enforcement with
                # --- multiple non-step-named files that come
                # --- from that department.
                # --- SSE -DW 2020-04-09
                if context.step["name"] == "Surfacing":
                    return "asset_step_surfacing"
                else:
                    return "asset_step"

        return None
