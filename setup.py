import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='drawable',
    version='0.0.1',
    author='Remi Rousseau',
    author_email='r_remi@hotmail.fr',
    description='Class tools to help design chips with HFSSdrawpy',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/RemiRousseau/drawable.git',
    license='MIT',
    packages=['drawable'],
    install_requires=[],
)