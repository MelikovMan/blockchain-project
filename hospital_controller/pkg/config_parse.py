import yaml

configPath = "config.yaml"


def get_config(obj):
    with open(configPath, 'r') as file:
        yaml_data = yaml.safe_load(file)

    config_obj = obj.model_validate(yaml_data)

    return config_obj
