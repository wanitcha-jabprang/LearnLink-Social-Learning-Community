def delete(files):
    for storage, name in files:
        storage.delete(name)
