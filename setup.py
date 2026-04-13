from setuptools import find_packages, setup

from pretix_i_ticket_multiticket_generator import __version__

setup(
    name="pretix-i-ticket-multiticket-generator",
    version=__version__,
    description="Multi ticket generator (i-ticket)",
    author="i-ticket",
    license="Apache Software License",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    entry_points="""
[pretix.plugin]
pretix_i_ticket_multiticket_generator=pretix_i_ticket_multiticket_generator:PretixPluginMeta
""",
)
