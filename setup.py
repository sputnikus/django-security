from setuptools import setup, find_packages

from security.version import get_version


setup(
    name='django-security-logger',
    version=get_version(),
    description="Django security library.",
    keywords='django, throttling',
    author='Lubos Matl',
    author_email='matllubos@gmail.com',
    url='https://github.com/matllubos/django-security',
    license='MIT',
    package_dir={'security': 'security'},
    include_package_data=True,
    packages=find_packages(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Czech',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
    ],
    install_requires=[
        'django>=1.6',
        'jsonfield>=1.0.3',
        'django-ipware>=1.0.0',
        'django-chamber>=0.3.6',
        'ansi2html>=1.3.0',
        'django-chamber>=0.4.0',
    ],
    zip_safe=False
)
