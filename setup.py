from setuptools import setup, find_packages

setup(
    name='pyvoicecontrol',
    version='0.1.0',
    description='Python Voice Control',
    author='Liam Wickins',
    author_email='liam9534@gmail.com',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.0',
    install_requires=['snapcast>=2.1.2',
                      'pykka>=3.0.0',
                      'requests>=2.25.1',
                      'pexpect>=4.8.0',
                      'spotipy>=2.17.1',
                      'nested-lookup>=0.2.22',
                      'evdev>=1.4.0',
                      'pulsectl-asyncio>=0.1.5'],
    extras_require={},
    entry_points={
        'console_scripts': [
            'pyvoicecontrol = pyvoicecontrol.__main__:main'
        ]
    },
)
