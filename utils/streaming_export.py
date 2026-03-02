import pandas as pd
import tempfile


def stream_to_csv(record_generator, chunk_size=5000):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    path = temp.name
    temp.close()

    first_chunk = True
    buffer = []

    for record in record_generator:
        buffer.append(record)

        if len(buffer) >= chunk_size:
            df = pd.DataFrame(buffer)
            df.to_csv(path, mode="a", index=False, header=first_chunk)
            first_chunk = False
            buffer = []

    if buffer:
        df = pd.DataFrame(buffer)
        df.to_csv(path, mode="a", index=False, header=first_chunk)

    return path
