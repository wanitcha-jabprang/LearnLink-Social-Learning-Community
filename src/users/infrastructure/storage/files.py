class FileStorage:
    def delete(self, files):
        for storage, name in files:
            storage.delete(name)
