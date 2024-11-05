from os import path, makedirs
from faker import Faker


def make(content: str, extension: str) -> str:
    faker = Faker()
    fname = faker.file_name(extension=extension)
    fpath = path.join("./tmp", fname)
    makedirs("./tmp", exist_ok=True)
    with open(fpath, "w") as f:
        f.write(content)

    return fpath, fname
