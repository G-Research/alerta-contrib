from setuptools import setup, find_packages

version = '1.0.0'

setup(
    name="alerta-jira",
    version=version,
    description='Alerta webhook for Jira',
    url='https://github.com/G-Research/alerta-contrib',
    license='MIT',
    author='James Kirsch',
    author_email='headphonejames@gmail.com',
    packages=find_packages(),
    py_modules=['alerta_jira'],
    install_requires=[
    ],
    include_package_data=True,
    zip_safe=True,
    entry_points={
        'alerta.webhooks': [
            'jira = alerta_jira:JiraWebhook'
        ]
    }
)
