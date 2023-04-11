from example_class import Qubit, Chip

qb = Qubit(
    folder="example/yaml_files",
    params="qubit_params.yaml",
    modeler=None,
    name="qb"
)

qb.create_yaml_file(filename="test.yaml")

chip = Chip(
    folder="example/yaml_files",
    params="chip_params.yaml",
    modeler=None,
    name="chip"
)

chip.create_variation_yaml_file(
    {"qubit.transmon.pad_dims": [["500um", "200um"], ["500um", "100um"]],
     "qubit.pos": [["-1mm", "0um"], ["1mm", "0um"]]},
    filename="test_variation.yaml"
)
