"""
Some database fixtures for our unit tests.
"""


from fixture import DataSet


def monkey_patch_fixture():
    """
    Fix fixture to support SQLAlchemy declarative model.

    SQLAlchemy declarative model definitions with custom constructor methods
    are note supported by fixture. Awaiting the pull request we monkey-patch
    fixture.

    Pull request: https://github.com/fixture-py/fixture/pull/2

    Call this function before importing anything from the fixture package. For
    example, start your file with the following:

        import fixtures; fixtures.monkey_patch_fixture()
        from fixture import DataSet, SQLAlchemyFixture
    """
    from fixture.loadable.sqlalchemy_loadable import MappedClassMedium

    def save(self, row, column_vals):
        """
        Save a new object to the session if it doesn't already exist in the
        session.
        """
        obj = self.medium(**dict(column_vals))
        if obj not in self.session.new:
            if hasattr(self.session, 'add'):
                # sqlalchemy 0.5.2+
                self.session.add(obj)
            else:
                self.session.save(obj)
        return obj

    MappedClassMedium.save = save


class UserData(DataSet):
    class test_user:
        name = 'Test User'
        login = 'test_login'
        password = 'test_password'


class SampleData(DataSet):
    class unactivated_sample:
        user = UserData.test_user
        name = 'Test Sample'


class DataSourceData(DataSet):
    class exome_samtools_coverage:
        user = UserData.test_user
        name = 'Test Data Source'
        filetype = 'bed'
        local_file = 'exome-samtools.bed'
    class exome_samtools_variation:
        user = UserData.test_user
        name = 'Test Data Source'
        filetype = 'vcf'
        local_file = 'exome-samtools.vcf'


class CoverageData(DataSet):
    class unimported_exome_samtools_coverage:
        sample = SampleData.unactivated_sample
        data_source = DataSourceData.exome_samtools_coverage
    class unimported_exome_samtools_coverage_2:
        sample = SampleData.unactivated_sample
        data_source = DataSourceData.exome_samtools_coverage


class VariationData(DataSet):
    class unimported_exome_samtools_variation:
        sample = SampleData.unactivated_sample
        data_source = DataSourceData.exome_samtools_variation
    class unimported_exome_samtools_variation_2:
        sample = SampleData.unactivated_sample
        data_source = DataSourceData.exome_samtools_variation
