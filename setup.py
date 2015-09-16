from distutils.core import setup

setup(
    name='move_bot',
    version='1.0.0',
    packages=['move_bot',
              'move_bot.components',
              'move_bot.components.commands',
              'move_bot.components.events',
              'move_bot.components.update_service',
              ],
    url='',
    license='BSD',
    author='Robert Robinson',
    author_email='rerobins@meerkatlabs.org',
    description='Moves App connection bot for the Rho infrastructure',
    install_requires=['rhobot==1.0.0', 'moves==0.1', 'requests==2.7.0', ]
)
