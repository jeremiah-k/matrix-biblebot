"""Tools and resources for BibleBot."""

import os
import pkg_resources

def get_sample_config_path():
    """Get the path to the sample config file."""
    return pkg_resources.resource_filename('biblebot.tools', 'sample_config.yaml')
