Class tools to help design chips with HFSSdrawpy.

Installation:

clone git repository (https://github.com/RemiRousseau/drawable.git)
Got to file location and run:
pip install .

This package contains two classes:

DrawableElement : Drawing object handeler. At init will parse the needed attributes. 
If they are not find in the config file, it will look for it in the parents folder.

Design (inherits from DrawableElement): Loads the configuration .yaml file at init an initalize the subclasses. 