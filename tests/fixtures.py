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


class _EmptyUpload(object):
    def read(self):
        return ''


class UserData(DataSet):
    class test_user:
        name = 'Test User'
        login = 'test_login'
        password = 'test_password'


class SampleData(DataSet):
    class exome_sample:
        user = UserData.test_user
        name = 'Exome sample'
    class exome_subset_sample:
        user = UserData.test_user
        name = 'Exome (subset) sample'
    class gonl_sample:
        user = UserData.test_user
        name = 'GoNL sample'
    class gonl_summary_sample:
        user = UserData.test_user
        name = 'GoNL (summary) sample'


class DataSourceData(DataSet):
    class exome_coverage:
        user = UserData.test_user
        name = 'Exome coverage'
        filetype = 'bed'
        local_file = 'exome.bed'
    class exome_variation:
        user = UserData.test_user
        name = 'Exome variants'
        filetype = 'vcf'
        local_file = 'exome.vcf'
    class exome_variation_filtered:
        user = UserData.test_user
        name = 'Exome variants (filtered)'
        filetype = 'vcf'
        local_file = 'exome-filtered.vcf'
    class exome_subset_coverage:
        user = UserData.test_user
        name = 'Exome (subset) coverage'
        filetype = 'bed'
        local_file = 'exome-subset.bed'
    class exome_subset_variation:
        user = UserData.test_user
        name = 'Exome (subset) variants'
        filetype = 'vcf'
        local_file = 'exome-subset.vcf'
    class gonl_variation:
        user = UserData.test_user
        name = 'GoNL variants'
        filetype = 'vcf'
        local_file = 'gonl.vcf'
    class gonl_summary_variation:
        user = UserData.test_user
        name = 'GoNL (summary) variants'
        filetype = 'vcf'
        local_file = 'gonl-summary.vcf'
    class empty_variation:
        user = UserData.test_user
        name = 'No variants'
        filetype = 'vcf'
        upload = _EmptyUpload()


class CoverageData(DataSet):
    class exome_coverage:
        sample = SampleData.exome_sample
        data_source = DataSourceData.exome_coverage
    class exome_coverage_duplicate:
        sample = SampleData.exome_sample
        data_source = DataSourceData.exome_coverage
    class exome_subset_coverage:
        sample = SampleData.exome_subset_sample
        data_source = DataSourceData.exome_subset_coverage


class VariationData(DataSet):
    class exome_variation:
        sample = SampleData.exome_sample
        data_source = DataSourceData.exome_variation
    class exome_variation_filtered:
        sample = SampleData.exome_sample
        data_source = DataSourceData.exome_variation_filtered
    class exome_variation_duplicate:
        sample = SampleData.exome_sample
        data_source = DataSourceData.exome_variation
    class exome_subset_variation:
        sample = SampleData.exome_subset_sample
        data_source = DataSourceData.exome_subset_variation


class AnnotationData(DataSet):
    class exome_annotation:
        original_data_source = DataSourceData.exome_variation
        annotated_data_source = DataSourceData.empty_variation
