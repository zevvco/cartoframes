import binascii as ba
from warnings import warn
import time

import pandas as pd
from carto.exceptions import CartoException
from carto.datasets import DatasetManager
from pyrestcli.exceptions import NotFoundException


class Dataset(object):
    SUPPORTED_GEOM_COL_NAMES = ['geom', 'the_geom', 'geometry']
    RESERVED_COLUMN_NAMES = SUPPORTED_GEOM_COL_NAMES + ['the_geom_webmercator', 'cartodb_id']

    FAIL = 'fail'
    REPLACE = 'replace'
    APPEND = 'append'

    PRIVATE = 'private'
    PUBLIC = 'public'
    LINK = 'link'

    MAX_RETRY_COUNT = 3
    WAIT_TIME = 3

    def __init__(self, carto_context, table_name, schema='public', df=None):
        self.cc = carto_context
        self.table_name = _norm_colname(table_name)
        self.schema = schema
        self.df = df
        warn('Table will be named `{}`'.format(table_name))

    def upload(self, with_lonlat=None, if_exists='fail', privacy='private'):
        if self.df is None:
            raise ValueError('You have to create a `Dataset` with a pandas DataFrame in order to upload it to CARTO')

        if not self.exists():
            self._create_table(with_lonlat)
        else:
            if if_exists == Dataset.FAIL:
                raise NameError(('Table with name {table_name} already exists in CARTO.'
                                 ' Please choose a different `table_name` or use'
                                 ' if_exists="replace" to overwrite it').format(table_name=self.table_name))
            elif if_exists == Dataset.REPLACE:
                self._create_table(with_lonlat)

        self._copyfrom(with_lonlat)

        dataset = self.get_carto_dataset()
        if dataset is not None:
            dataset.privacy = privacy
            dataset.save()

        return self

    def download(self, limit=None, decode_geom=False):
        table_columns = self._get_table_columns()

        query = self._get_read_query(table_columns, limit)
        result = self.cc.copy_client.copyto_stream(query)
        df = pd.read_csv(result)

        return _clean_dataframe_from_carto(df, table_columns, decode_geom)

    def exists(self):
        """Checks to see if table exists"""
        try:
            self.cc.sql_client.send(
                'EXPLAIN SELECT * FROM "{table_name}"'.format(
                    table_name=self.table_name),
                do_post=False)
            return True
        except CartoException as err:
            # If table doesn't exist, we get an error from the SQL API
            self.cc._debug_print(err=err)
            return False

    def get_carto_dataset(self):
        dataset = self._do_get_carto_dataset()
        if dataset is not None:
            return dataset

        retry = 0
        while retry <= Dataset.MAX_RETRY_COUNT:
            dataset = self._do_get_carto_dataset()
            if dataset is not None:
                break
            time.sleep(Dataset.WAIT_TIME)

        return dataset

    def _do_get_carto_dataset(self):
        try:
            return DatasetManager(self.cc.auth_client).get(self.table_name)
        except NotFoundException:
            return None

    def _create_table(self, with_lonlat=None):
        job = self.cc.batch_sql_client \
                  .create_and_wait_for_completion(
                      '''BEGIN; {drop}; {create}; {cartodbfy}; COMMIT;'''
                      .format(drop=self._drop_table_query(),
                              create=self._create_table_query(with_lonlat),
                              cartodbfy=self._cartodbfy_query()))

        if job['status'] != 'done':
            raise CartoException('Cannot create table: {}.'.format(job['failed_reason']))

    def _cartodbfy_query(self):
        return "SELECT CDB_CartodbfyTable('{org}', '{table_name}')" \
            .format(org=(self.cc.creds.username() if self.cc.is_org else 'public'),
                    table_name=self.table_name)

    def _copyfrom(self, with_lonlat=None):
        geom_col = _get_geom_col_name(self.df)

        columns = ','.join(_norm_colname(c) for c in self.df.columns if c not in Dataset.RESERVED_COLUMN_NAMES)
        self.cc.copy_client.copyfrom(
            """COPY {table_name}({columns},the_geom)
               FROM stdin WITH (FORMAT csv, DELIMITER '|');""".format(table_name=self.table_name, columns=columns),
            self._rows(self.df, self.df.columns, with_lonlat, geom_col)
        )

    def _rows(self, df, cols, with_lonlat, geom_col):
        for i, row in df.iterrows():
            csv_row = ''
            the_geom_val = None
            for col in cols:
                if with_lonlat and col in Dataset.SUPPORTED_GEOM_COL_NAMES:
                    continue
                val = row[col]
                if pd.isnull(val) or val is None:
                    val = ''
                if with_lonlat:
                    if col == with_lonlat[0]:
                        lng_val = row[col]
                    if col == with_lonlat[1]:
                        lat_val = row[col]
                if col == geom_col:
                    the_geom_val = row[col]
                else:
                    csv_row += '{val}|'.format(val=val)

            if the_geom_val is not None:
                geom = _decode_geom(the_geom_val)
                if geom:
                    csv_row += 'SRID=4326;{geom}'.format(geom=geom.wkt)
            if with_lonlat is not None:
                csv_row += 'SRID=4326;POINT({lng} {lat})'.format(lng=lng_val, lat=lat_val)

            csv_row += '\n'
            yield csv_row.encode()

    def _drop_table_query(self):
        return '''DROP TABLE IF EXISTS {table_name}'''.format(table_name=self.table_name)

    def _create_table_query(self, with_lonlat=None):
        if with_lonlat is None:
            geom_type = _get_geom_col_type(self.df)
        else:
            geom_type = 'Point'

        col = ('{col} {ctype}')
        cols = ', '.join(col.format(col=_norm_colname(c),
                                    ctype=_dtypes2pg(t))
                         for c, t in zip(self.df.columns, self.df.dtypes) if c not in Dataset.RESERVED_COLUMN_NAMES)

        if geom_type:
            cols += ', {geom_colname} geometry({geom_type}, 4326)'.format(geom_colname='the_geom', geom_type=geom_type)

        create_query = '''CREATE TABLE {table_name} ({cols})'''.format(table_name=self.table_name, cols=cols)
        return create_query

    def _get_read_query(self, table_columns, limit=None):
        """Create the read (COPY TO) query"""
        query_columns = list(table_columns.keys())
        query_columns.remove('the_geom_webmercator')

        query = 'SELECT {columns} FROM "{schema}"."{table_name}"'.format(
            table_name=self.table_name,
            schema=self.schema,
            columns=', '.join(query_columns))

        if limit is not None:
            if isinstance(limit, int) and (limit >= 0):
                query += ' LIMIT {limit}'.format(limit=limit)
            else:
                raise ValueError("`limit` parameter must an integer >= 0")

        return 'COPY ({query}) TO stdout WITH (FORMAT csv, HEADER true)'.format(query=query)

    def _get_table_columns(self):
        """Get column names and types from a table"""
        query = 'SELECT * FROM "{schema}"."{table}" limit 0'.format(table=self.table_name, schema=self.schema)
        table_info = self.cc.sql_client.send(query)
        if 'fields' in table_info:
            return table_info['fields']

        return None


def _norm_colname(colname):
    """Given an arbitrary column name, translate to a SQL-normalized column
    name a la CARTO's Import API will translate to

    Examples
        * 'Field: 2' -> 'field_2'
        * '2 Items' -> '_2_items'

    Args:
        colname (str): Column name that will be SQL normalized
    Returns:
        str: SQL-normalized column name
    """
    last_char_special = False
    char_list = []
    for colchar in str(colname):
        if colchar.isalnum():
            char_list.append(colchar.lower())
            last_char_special = False
        else:
            if not last_char_special:
                char_list.append('_')
                last_char_special = True
            else:
                last_char_special = False
    final_name = ''.join(char_list)
    if final_name[0].isdigit():
        return '_' + final_name
    return final_name


def _dtypes2pg(dtype):
    """Returns equivalent PostgreSQL type for input `dtype`"""
    mapping = {
        'float64': 'numeric',
        'int64': 'numeric',
        'float32': 'numeric',
        'int32': 'numeric',
        'object': 'text',
        'bool': 'boolean',
        'datetime64[ns]': 'timestamp',
        'datetime64[ns, UTC]': 'timestamp',
    }
    return mapping.get(str(dtype), 'text')


def _get_geom_col_name(df):
    geom_col = getattr(df, '_geometry_column_name', None)
    if geom_col is None:
        try:
            geom_col = next(x for x in df.columns if x.lower() in Dataset.SUPPORTED_GEOM_COL_NAMES)
        except StopIteration:
            pass

    return geom_col


def _get_geom_col_type(df):
    geom_col = _get_geom_col_name(df)
    if geom_col is None:
        return None

    try:
        geom = _decode_geom(_first_not_null_value(df, geom_col))
    except IndexError:
        warn('Dataset with null geometries')
        geom = None

    if geom is None:
        return None

    return geom.geom_type


def _first_not_null_value(df, col):
    return df[col].loc[~df[col].isnull()].iloc[0]


def _encode_decode_decorator(func):
    """decorator for encoding and decoding geoms"""
    def wrapper(*args):
        """error catching"""
        try:
            processed_geom = func(*args)
            return processed_geom
        except ImportError as err:
            raise ImportError('The Python package `shapely` needs to be '
                              'installed to encode or decode geometries. '
                              '({})'.format(err))
    return wrapper


@_encode_decode_decorator
def _decode_geom(ewkb):
    """Decode encoded wkb into a shapely geometry
    """
    # it's already a shapely object
    if hasattr(ewkb, 'geom_type'):
        return ewkb

    from shapely import wkb
    from shapely import wkt
    if ewkb:
        try:
            return wkb.loads(ba.unhexlify(ewkb))
        except Exception:
            try:
                return wkb.loads(ba.unhexlify(ewkb), hex=True)
            except Exception:
                try:
                    return wkb.loads(ewkb, hex=True)
                except Exception:
                    try:
                        return wkb.loads(ewkb)
                    except Exception:
                        try:
                            return wkt.loads(ewkb)
                        except Exception:
                            pass
    return None


def _clean_dataframe_from_carto(df, table_columns, decode_geom=False):
    """Clean a DataFrame with a dataset from CARTO:
        - use cartodb_id as DataFrame index
        - process date columns
        - decode geom

    Args:
        df (pandas.DataFrame): DataFrame with a dataset from CARTO.
        table_columns (dict): column names and types from a table.
        decode_geom (bool, optional): Decodes CARTO's geometries into a
            `Shapely <https://github.com/Toblerity/Shapely>`__
            object that can be used, for example, in `GeoPandas
            <http://geopandas.org/>`__.

    Returns:
        pandas.DataFrame
    """
    if 'cartodb_id' in df.columns:
        df.set_index('cartodb_id', inplace=True)

    for column_name in table_columns:
        if table_columns[column_name]['type'] == 'date':
            df[column_name] = pd.to_datetime(df[column_name], errors='ignore')

    if decode_geom:
        df['geometry'] = df.the_geom.apply(_decode_geom)

    return df
