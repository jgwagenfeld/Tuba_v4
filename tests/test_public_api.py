import unittest


class TestPublicApi(unittest.TestCase):
    def test_architecture_interfaces_are_exported(self):
        from tuba import (
            AddElement,
            AddInsulationSpec,
            AddNode,
            AddSupport,
            AssignAttribute,
            AttributeAssignment,
            ClashFreeRule,
            ClashResult,
            CoordinateSystem,
            CreateGroup,
            ElementPhysicalProperties,
            ElementQuantities,
            EntityRef,
            InsulationSpec,
            LoadPathReport,
            MODEL_SCHEMA_V4,
            PATCH_SCHEMA_V1,
            Model,
            ModelFragment,
            ModelPatch,
            ModelTransaction,
            PlacementResult,
            QuantityRecord,
            QuantityTakeoff,
            RackBay,
            RuleEngine,
            RuleReport,
            RuleResult,
            SchemaValidationError,
            SectionCatalog,
            SupportRackAssociation,
            SupportSpacingRule,
            TrimeshClashEngine,
            analyze_load_paths,
            clash_report_to_dict,
            clash_report_to_markdown,
            element_length,
            element_quantities,
            physical_properties_for_element,
            quantity_takeoff,
            resolve_entity_ref,
            rule_report_to_markdown,
            validate_model_dict,
            validate_patch_dict,
            wind_loads,
            write_model_benchmark_summary,
        )

        self.assertIsNotNone(Model)
        self.assertIsNotNone(CoordinateSystem)
        self.assertIsNotNone(ModelFragment)
        self.assertIsNotNone(PlacementResult)
        self.assertIsNotNone(AddElement)
        self.assertIsNotNone(AddInsulationSpec)
        self.assertIsNotNone(AddNode)
        self.assertIsNotNone(AddSupport)
        self.assertIsNotNone(AssignAttribute)
        self.assertIsNotNone(CreateGroup)
        self.assertIsNotNone(ModelPatch)
        self.assertIsNotNone(ModelTransaction)
        self.assertIsNotNone(AttributeAssignment)
        self.assertIsNotNone(InsulationSpec)
        self.assertIsNotNone(RackBay)
        self.assertIsNotNone(ElementPhysicalProperties)
        self.assertIsNotNone(ElementQuantities)
        self.assertIsNotNone(QuantityRecord)
        self.assertIsNotNone(QuantityTakeoff)
        self.assertIsNotNone(LoadPathReport)
        self.assertIsNotNone(SupportRackAssociation)
        self.assertIsNotNone(ClashFreeRule)
        self.assertIsNotNone(RuleEngine)
        self.assertIsNotNone(RuleReport)
        self.assertIsNotNone(RuleResult)
        self.assertIsNotNone(SupportSpacingRule)
        self.assertIsNotNone(ClashResult)
        self.assertIsNotNone(TrimeshClashEngine)
        self.assertIsNotNone(EntityRef)
        self.assertIsNotNone(element_length)
        self.assertIsNotNone(element_quantities)
        self.assertIsNotNone(physical_properties_for_element)
        self.assertIsNotNone(quantity_takeoff)
        self.assertIsNotNone(wind_loads)
        self.assertIsNotNone(analyze_load_paths)
        self.assertIsNotNone(rule_report_to_markdown)
        self.assertIsNotNone(write_model_benchmark_summary)
        self.assertIsNotNone(clash_report_to_dict)
        self.assertIsNotNone(clash_report_to_markdown)
        self.assertIsNotNone(resolve_entity_ref)
        self.assertIsNotNone(MODEL_SCHEMA_V4)
        self.assertIsNotNone(PATCH_SCHEMA_V1)
        self.assertIsNotNone(SchemaValidationError)
        self.assertIsNotNone(SectionCatalog)
        self.assertIsNotNone(validate_model_dict)
        self.assertIsNotNone(validate_patch_dict)


if __name__ == "__main__":
    unittest.main()
