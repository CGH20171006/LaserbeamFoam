/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  2506                                  |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    arch        "LSB;label=32;scalar=64";
    class       surfaceScalarField;
    location    "0.002";
    object      alphaPhi0.metal;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 3 -1 0 0 0 0];

oriented        oriented;

internalField   uniform 0;

boundaryField
{
    lowerWall
    {
        type            calculated;
        value           uniform 0;
    }
    atmosphere
    {
        type            calculated;
        value           uniform 0;
    }
    rightWall
    {
        type            empty;
    }
    leftWall
    {
        type            empty;
    }
    frontAndBack
    {
        type            calculated;
        value           uniform 0;
    }
}


// ************************************************************************* //
