
from .enrichment_service import EnrichmentService


class Enrichment(EnrichmentService):

    def __init__(self, credentials=None):
        """
        Dataset enrichment with `Data Observatory <https://carto.com/platform/location-data-streams/>` data

        Args:
            credentials (:py:class:`Credentials <cartoframes.auth.Credentials>`, optional):
                credentials of user account. If not provided,
                a default credentials (if set with :py:meth:`set_default_credentials
                <cartoframes.auth.set_default_credentials>`) will attempted to be
                used.
        """

        super(Enrichment, self).__init__(credentials)

    def enrich_points(self, data, variables, data_geom_column='geometry', filters={}, **kwargs):
        """Enrich your dataset with columns from our data, intersecting your points with our
        geographies. Extra columns as area and population will be provided with the aims of normalize
        these columns.

        Args:
            data (:py:class:`Dataset <cartoframes.data.Dataset>`, DataFrame, GeoDataFrame):
                a Dataset, DataFrame or GeoDataFrame object to be enriched.
            variables (:py:class:`Variable <cartoframes.data.observatory.Catalog>`, CatalogList, list, str):
                variable(s), discovered through Catalog, for enriching the `data` argument.
            data_geom_column (str): string indicating the 4326 geometry column in `data`.
            filters (dict, optional): dictionary with either a `column` key
                with the name of the column to filter or a `value` value with the value to filter by.
                Filters will be used using the `AND` operator

        Returns:
            A DataFrame as the provided one, but with the variables to enrich appended to it.

            Note that if the geometry of the `data` you provide intersects with more than one geometry
            in the enrichment dataset, the number of rows of the returned DataFrame could be different
            than the `data` argument number of rows.

        Examples:

            Enrich a points dataset with Catalog classes:

            .. code::

                from cartoframes.data.observatory import Enrichment, Catalog
                from cartoframes.auth import set_default_credentials

                set_default_credentials('YOUR_USER_NAME', 'YOUR_API_KEY')

                catalog = Catalog()
                enrichment = Enrichment()

                variables = catalog.country('usa').category('demographics').datasets[0].variables
                dataset_enrich = enrichment.enrich_points(dataset, variables)


            Enrich a points dataset with list of ids:

            .. code::

                from cartoframes.data.observatory import Enrichment
                from cartoframes.auth import set_default_credentials

                set_default_credentials('YOUR_USER_NAME', 'YOUR_API_KEY')

                enrichment = Enrichment()

                variables = [
                    'carto-do-public-data.acsquantiles.demographics_acsquantiles_usa_schooldistrictelementaryclipped_2015_5yrs_20062010.in_grades_1_to_4_quantile',
                    'carto-do-public-data.acsquantiles.demographics_acsquantiles_usa_schooldistrictelementaryclipped_2015_5yrs_20062010.in_school_quantile'
                ]

                dataset_enrich = enrichment.enrich_points(dataset, variables)


            Enrich a points dataset filtering our data:

            .. code::

                from cartoframes.data.observatory import Enrichment, Catalog
                from cartoframes.auth import set_default_credentials

                set_default_credentials('YOUR_USER_NAME', 'YOUR_API_KEY')

                catalog = Catalog()
                enrichment = Enrichment()

                variables = catalog.country('usa').category('demographics').datasets[0].variables
                filters = {'do_date': '2019-09-01'}
                dataset_enrich = enrichment.enrich_points(dataset, variables, filters)
        """

        variables = self._prepare_variables(variables)
        data_copy = self._prepare_data(data, data_geom_column)

        temp_table_name = self._get_temp_table_name()
        self._upload_dataframe(temp_table_name, data_copy, data_geom_column)

        queries = self._prepare_points_enrichment_sql(temp_table_name, data_geom_column, variables, filters)

        return self._execute_enrichment(queries, data_copy, data_geom_column)

    def enrich_polygons(self, data, variables, data_geom_column='geometry', filters={}, agg_operators={}, **kwargs):
        """Enrich your dataset with columns from our data, intersecting your polygons with our geographies.
        When a polygon intersects with multiple geographies of our dataset, the proportional part of the
        intersection will be used to interpolate the quantity of the polygon value intersected, aggregating them
        with the operator provided by `agg_operators` argument.

        Args:
            data (Dataset, DataFrame, GeoDataFrame): a Dataset, DataFrame or GeoDataFrame object to be enriched.
            variables (Variable, CatalogList, list, str): variable(s), discovered through Catalog,
                for enriching the `data` argument.
            data_geom_column (str): string indicating the 4326 geometry column in `data`.
            filters (dict, optional): dictionary with either a `column` key
                with the name of the column to filter or a `value` value with the value to filter by.
            agg_operators (dict, str, None, optional): dictionary with either a `column` key
                with the name of the column to aggregate or a `operator` value with the operator to group by.
                If `agg_operators`' dictionary is empty (default argument value) then aggregation operators
                will be retrieved from metadata column.
                If `agg_operators` is a string then all columns will be aggregated by this operator.
                If `agg_operators` is `None` then the default `array_agg` function will be used. Since we're
                using a `group by` clause, all the values which data geometry intersects with will be returned
                in the array.

        Returns:
            A DataFrame as the provided one but with the variables to enrich appended to it

            Note that if the geometry of the `data` you provide intersects with more than one geometry
            in the enrichment dataset, the number of rows of the returned DataFrame could be different
            than the `data` argument number of rows.

        Examples:

            Enrich a polygons dataset with Catalog classes and default aggregation methods:

            .. code::

                from cartoframes.data.observatory import Enrichment, Catalog
                from cartoframes.auth import set_default_credentials

                set_default_credentials('YOUR_USER_NAME', 'YOUR_API_KEY')

                catalog = Catalog()
                enrichment = Enrichment()

                variables = catalog.country('usa').category('demographics').datasets[0].variables
                dataset_enrich = enrichment.enrich_polygons(dataset, variables)


            Enrich a polygons dataset with list of ids:

            .. code::

                from cartoframes.data.observatory import Enrichment
                from cartoframes.auth import set_default_credentials

                set_default_credentials('YOUR_USER_NAME', 'YOUR_API_KEY')

                enrichment = Enrichment()

                variables = [
                    'carto-do-public-data.acsquantiles.demographics_acsquantiles_usa_schooldistrictelementaryclipped_2015_5yrs_20062010.in_grades_1_to_4_quantile',
                    'carto-do-public-data.acsquantiles.demographics_acsquantiles_usa_schooldistrictelementaryclipped_2015_5yrs_20062010.in_school_quantile'
                ]

                dataset_enrich = enrichment.enrich_polygons(dataset, variables)


            Enrich a polygons dataset filtering our data:

            .. code::

                from cartoframes.data.observatory import Enrichment, Catalog
                from cartoframes.auth import set_default_credentials

                set_default_credentials('YOUR_USER_NAME', 'YOUR_API_KEY')

                catalog = Catalog()
                enrichment = Enrichment()

                variables = catalog.country('usa').category('demographics').datasets[0].variables
                filters = {'do_date': '2019-09-01'}

                dataset_enrich = enrichment.enrich_polygons(dataset, variables, filters)


            Enrich a polygons dataset with custom aggregation methods:

            .. code::

                from cartoframes.data.observatory import Enrichment
                from cartoframes.auth import set_default_credentials

                set_default_credentials('YOUR_USER_NAME', 'YOUR_API_KEY')

                enrichment = Enrichment()

                variables = [
                    'carto-do-public-data.acsquantiles.demographics_acsquantiles_usa_schooldistrictelementaryclipped_2015_5yrs_20062010.in_grades_1_to_4_quantile',
                    'carto-do-public-data.acsquantiles.demographics_acsquantiles_usa_schooldistrictelementaryclipped_2015_5yrs_20062010.in_school_quantile'
                ]

                agg_operators = {'in_grades_1_to_4_quantile': 'SUM', 'in_school_quantile': 'AVG'}
                dataset_enrich = enrichment.enrich_polygons(dataset, variables, agg_operators=agg_operators)

            Enrich a polygons dataset with no aggregation methods:

            .. code::

                from cartoframes.data.observatory import Enrichment
                from cartoframes.auth import set_default_credentials

                set_default_credentials('YOUR_USER_NAME', 'YOUR_API_KEY')

                enrichment = Enrichment()

                variables = [
                    'carto-do-public-data.acsquantiles.demographics_acsquantiles_usa_schooldistrictelementaryclipped_2015_5yrs_20062010.in_grades_1_to_4_quantile',
                    'carto-do-public-data.acsquantiles.demographics_acsquantiles_usa_schooldistrictelementaryclipped_2015_5yrs_20062010.in_school_quantile'
                ]

                agg_operators = None
                dataset_enrich = enrichment.enrich_polygons(dataset, variables, agg_operators=agg_operators)
        """

        variables = self._prepare_variables(variables)
        data_copy = self._prepare_data(data, data_geom_column)

        temp_table_name = self._get_temp_table_name()
        self._upload_dataframe(temp_table_name, data_copy, data_geom_column)

        queries = self._prepare_polygon_enrichment_sql(
            temp_table_name, data_geom_column, variables, filters, agg_operators
        )

        return self._execute_enrichment(queries, data_copy, data_geom_column)

    def _prepare_points_enrichment_sql(self, temp_table_name, data_geom_column, variables, filters):
        filters = self._process_filters(filters)
        tables_metadata = self._get_tables_metadata(variables).items()

        sqls = list()

        for table, metadata in tables_metadata:
            sqls.append(self._build_points_query(table, metadata, temp_table_name, data_geom_column, filters))

        return sqls

    def _prepare_polygon_enrichment_sql(self, temp_table_name, data_geom_column, variables, filters, agg_operators):
        filters_str = self._process_filters(filters)
        agg_operators = self._process_agg_operators(agg_operators, variables, default_agg='ARRAY_AGG')
        tables_metadata = self._get_tables_metadata(variables).items()

        if agg_operators:
            grouper = 'group by data_table.{enrichment_id}'.format(enrichment_id=self.enrichment_id)

        sqls = list()

        for table, metadata in tables_metadata:
            sqls.append(self._build_polygons_query(
                table, metadata, temp_table_name, data_geom_column, agg_operators, filters_str, grouper)
            )

        return sqls

    def _build_points_query(self, table, metadata, temp_table_name, data_geom_column, filters):
        variables = ', '.join(
            ['enrichment_table.{}'.format(variable) for variable in metadata['variables']])
        enrichment_dataset = metadata['dataset']
        enrichment_geo_table = metadata['geo_table']
        data_table = '{project}.{user_dataset}.{temp_table_name}'.format(
            project=self.working_project,
            user_dataset=self.user_dataset,
            temp_table_name=temp_table_name
        )

        return '''
            SELECT data_table.{enrichment_id},
                {variables},
                ST_Area(enrichment_geo_table.geom) AS {table}_area
            FROM `{enrichment_dataset}` enrichment_table
                JOIN `{enrichment_geo_table}` enrichment_geo_table
                    ON enrichment_table.geoid = enrichment_geo_table.geoid
                JOIN `{data_table}` data_table
                    ON ST_Within(data_table.{data_geom_column}, enrichment_geo_table.geom)
            {filters};
        '''.format(
            data_geom_column=data_geom_column,
            enrichment_dataset=enrichment_dataset,
            enrichment_geo_table=enrichment_geo_table,
            enrichment_id=self.enrichment_id,
            filters=filters,
            data_table=data_table,
            table=table,
            variables=variables
        )

    def _build_polygons_query(self, table, metadata, temp_table_name, data_geom_column, agg_operators,
                              filters, grouper):
        variables_list = metadata['variables']
        enrichment_dataset = metadata['dataset']
        enrichment_geo_table = metadata['geo_table']
        data_table = '{project}.{user_dataset}.{temp_table_name}'.format(
            project=self.working_project,
            user_dataset=self.user_dataset,
            temp_table_name=temp_table_name
        )

        variables = self._build_query_variables(agg_operators, variables_list, data_geom_column)

        return '''
            SELECT data_table.{enrichment_id},
                {variables}
            FROM `{enrichment_dataset}` enrichment_table
                JOIN `{enrichment_geo_table}` enrichment_geo_table
                    ON enrichment_table.geoid = enrichment_geo_table.geoid
                JOIN `{data_table}` data_table
                    ON ST_Intersects(data_table.{data_geom_column}, enrichment_geo_table.geom)
            {filters}
            {grouper};
        '''.format(
                data_geom_column=data_geom_column,
                enrichment_dataset=enrichment_dataset,
                enrichment_geo_table=enrichment_geo_table,
                enrichment_id=self.enrichment_id,
                filters=filters,
                data_table=data_table,
                grouper=grouper or '',
                variables=variables
            )

    def _build_query_variables(self, agg_operators, variables, data_geom_column):
        sql_variables = []

        if agg_operators is not None:
            sql_variables = ['{operator}(enrichment_table.{variable} * \
                (ST_Area(ST_Intersection(enrichment_geo_table.geom, data_table.{data_geom_column}))\
                / ST_area(data_table.{data_geom_column}))) AS {variable}'.format(
                    variable=variable,
                    data_geom_column=data_geom_column,
                    operator=agg_operators.get(variable)) for variable in variables]
        else:
            sql_variables = ['enrichment_table.{}'.format(variable) for variable in variables] + \
                ['ST_Area(ST_Intersection(enrichment_geo_table.geom, data_table.{data_geom_column}))\
                    / ST_area(data_table.{data_geom_column}) AS measures_proportion'.format(
                        data_geom_column=data_geom_column)]

        return ', '.join(sql_variables)