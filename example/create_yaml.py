from example_class import Qubit

qb = Qubit(
    folder="example/yaml_files",
    params="qubit_params.yaml",
    modeler=None,
    name="qb"
)

qb.create_yaml_file(filename="test.yaml")
