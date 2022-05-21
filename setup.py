from setuptools import find_packages, setup

setup(name='dearmor',
      version='0.0',
      description='Deobfuscate pyarmor files',
      author='Erez Amihud',
      author_email='erezamihud@gmail.com',
      url='https://github.com/ErezAmihud/dearmor',
      packages=['dearmor'],
      requires=['pyinjector', 'psutil'],
      extras_require={"test": "pytest"},
      package_data={
        'code': ['code.py'],
      },
      entry_points={
                        'console_scripts': [
                                'dearmor=dearmor.__main__:main_cli',
                        ]
                }
     )