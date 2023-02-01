from setuptools import setup, find_packages

version = '1.0.0'

setup(
    name="alerta-jira",
    version=version,
    description='Alerta plugin for create tasks in jira',
    url='https://github.com/G-Research/alerta-contrib',
    license='MIT',
    author='James Kirsch',
    author_email='headphonejames@gmail.com',
    packages=find_packages(),
    py_modules=['alerta_jira'],
    include_package_data=True,
    zip_safe=True,
    entry_points={
        'alerta.plugins': [
            'jira = alerta_jira:JiraCreate'
        ]
    },
    install_requires=[
        'jira',
        'alerta'
    ],
)
